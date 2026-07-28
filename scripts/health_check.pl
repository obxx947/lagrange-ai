#!/usr/bin/perl
#
# Lagrange Agent Server - Health Check Script
# Checks HTTP endpoint, database connectivity, disk space, process status,
# and Python environment integrity for the Infinite Lagrange tactical analysis tool.
#

use strict;
use warnings;
use 5.010;

# ---- Configuration ----
my $HTTP_URL       = $ENV{LAGRANGE_HTTP_URL}       // "http://127.0.0.1:8080/api/health";
my $DB_FILE        = $ENV{LAGRANGE_DB_PATH}        // "data/lagrange.db";
my $PID_FILE       = $ENV{LAGRANGE_PID_FILE}       // "logs/server.pid";
my $PYTHON_BIN     = $ENV{LAGRANGE_PYTHON}         // "python";
my $LOG_FILE       = $ENV{LAGRANGE_LOG_FILE}       // "logs/health_check.log";
my $MIN_DISK_FREE_MB = $ENV{LAGRANGE_MIN_DISK_MB} // 500;
my $HTTP_TIMEOUT   = 10;
my $EXIT_CODE      = 0;

# ---- Helpers ----
sub log_msg {
    my ($level, $msg) = @_;
    my $ts = localtime();
    my $line = "[$ts] [$level] $msg\n";
    print $line;
    if (open(my $fh, '>>', $LOG_FILE)) {
        print $fh $line;
        close($fh);
    }
}

sub fail {
    my ($msg) = @_;
    log_msg("FAIL", $msg);
    $EXIT_CODE = 1;
}

sub ok {
    my ($msg) = @_;
    log_msg("OK", $msg);
}

# ---- 1. HTTP Endpoint Check ----
sub check_http {
    log_msg("INFO", "Checking HTTP endpoint: $HTTP_URL");

    eval { require LWP::Simple; };
    if ($@) {
        # Fallback: use curl or a raw socket
        my $out = `curl -s -o /dev/null -w "%{http_code}" --max-time $HTTP_TIMEOUT "$HTTP_URL" 2>&1`;
        if ($? == 0 && $out =~ /^(2\d\d|3\d\d)$/) {
            ok("HTTP endpoint responded with status $out");
        } else {
            fail("HTTP endpoint check failed: $out");
        }
        return;
    }

    my $content = LWP::Simple::get($HTTP_URL);
    if (defined $content) {
        ok("HTTP endpoint reachable");
    } else {
        fail("HTTP endpoint unreachable at $HTTP_URL");
    }
}

# ---- 2. Database Check ----
sub check_database {
    log_msg("INFO", "Checking SQLite database: $DB_FILE");

    unless (-e $DB_FILE) {
        fail("Database file not found: $DB_FILE");
        return;
    }

    eval { require DBI; };
    if ($@) {
        # Fallback: use sqlite3 CLI
        my $out = `sqlite3 "$DB_FILE" "SELECT count(*) FROM ships;" 2>&1`;
        if ($? == 0) {
            ok("Database accessible, ship count: " . ($out // "unknown"));
        } else {
            fail("Database query failed: $out");
        }
        return;
    }

    my $dbh = DBI->connect("dbi:SQLite:dbname=$DB_FILE", "", "", {
        RaiseError => 0, PrintError => 0, AutoCommit => 1
    });
    if ($dbh) {
        my $count = $dbh->selectrow_array("SELECT count(*) FROM ships");
        ok("Database connected, ships in DB: " . ($count // 0));
        $dbh->disconnect;
    } else {
        fail("Database connection failed for $DB_FILE");
    }
}

# ---- 3. Disk Space Check ----
sub check_disk {
    log_msg("INFO", "Checking disk space (min free: ${MIN_DISK_FREE_MB}MB)");

    my $disk_line;
    if ($^O eq 'MSWin32') {
        $disk_line = `wmic logicaldisk where "DeviceID='C:'" get FreeSpace,Size /format:csv 2>&1`;
        if ($disk_line =~ /(\d+),\s*(\d+),\s*(\d+)/) {
            my $free_mb = int($3 / (1024 * 1024));
            if ($free_mb >= $MIN_DISK_FREE_MB) {
                ok("Disk space OK: ${free_mb}MB free");
            } else {
                fail("Low disk space: ${free_mb}MB free (need ${MIN_DISK_FREE_MB}MB)");
            }
        } else {
            fail("Could not parse disk info from wmic output");
        }
    } else {
        $disk_line = `df -BM . 2>&1`;
        if ($disk_line =~ /(\d+)M\s+\d+M\s+(\d+)M/) {
            my $free_mb = $2;
            if ($free_mb >= $MIN_DISK_FREE_MB) {
                ok("Disk space OK: ${free_mb}MB free");
            } else {
                fail("Low disk space: ${free_mb}MB free (need ${MIN_DISK_FREE_MB}MB)");
            }
        } else {
            fail("Could not parse disk info from df output");
        }
    }
}

# ---- 4. Process Check ----
sub check_process {
    log_msg("INFO", "Checking server process (PID file: $PID_FILE)");

    unless (-e $PID_FILE) {
        fail("PID file not found: $PID_FILE");
        return;
    }

    open(my $fh, '<', $PID_FILE) or do {
        fail("Cannot read PID file: $!");
        return;
    };
    my $pid = <$fh>;
    close($fh);
    chomp $pid;

    if ($pid !~ /^\d+$/) {
        fail("Invalid PID in PID file: $pid");
        return;
    }

    if ($^O eq 'MSWin32') {
        my $tasklist = `tasklist /FI "PID eq $pid" 2>&1`;
        if ($tasklist =~ /python/i || $tasklist =~ /lagrange/i) {
            ok("Server process running with PID $pid");
        } else {
            fail("Server process PID $pid not found in tasklist");
        }
    } else {
        if (kill(0, $pid)) {
            ok("Server process running with PID $pid");
        } else {
            fail("Server process PID $pid is not running");
        }
    }
}

# ---- 5. Python Environment Check ----
sub check_python {
    log_msg("INFO", "Checking Python environment");

    my $ver = `$PYTHON_BIN --version 2>&1`;
    if ($? == 0) {
        chomp $ver;
        ok("Python available: $ver");
    } else {
        fail("Python binary '$PYTHON_BIN' not functional");
        return;
    }

    # Check critical Python packages
    my @required = qw(numpy pandas sqlalchemy flask jinja2);
    my $code = "import " . join(", ", @required);
    my $result = `$PYTHON_BIN -c "$code; print('ALL_OK')" 2>&1`;
    if ($result =~ /ALL_OK/) {
        ok("All critical Python packages available: @required");
    } else {
        $result =~ s/\n/ /g;
        fail("Python package check failed: $result");
    }
}

# ---- 6. Log Directory Check ----
sub check_logs {
    log_msg("INFO", "Checking log directory");
    my $log_dir = "logs";
    if (-d $log_dir && -w $log_dir) {
        my @log_files = glob("$log_dir/*.log");
        ok("Log directory writable, " . scalar(@log_files) . " log files present");
    } elsif (-d $log_dir) {
        fail("Log directory exists but is not writable");
    } else {
        fail("Log directory missing: $log_dir");
    }
}

# ---- Main ----
sub main {
    log_msg("INFO", "=== Lagrange Agent Health Check Started ===");

    check_http();
    check_database();
    check_disk();
    check_process();
    check_python();
    check_logs();

    log_msg("INFO", "=== Health Check Complete, exit code: $EXIT_CODE ===");
    exit $EXIT_CODE;
}

main();
