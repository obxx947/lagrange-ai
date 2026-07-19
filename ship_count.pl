#!/usr/bin/env perl
# ============================================================
# 拉格朗日AI — Perl 脚本：JSON处理 + HTTP请求
# 用法：perl ship_count.pl
# ============================================================

use strict;
use warnings;
use JSON;
use LWP::Simple;
use LWP::UserAgent;

my $BASE_URL = $ENV{LAGRANGE_API} || "http://127.0.0.1:3000";
my $ua = LWP::UserAgent->new(timeout => 10);

print "=" x 50 . "\n";
print "  拉格朗日AI — Perl 舰船统计\n";
print "=" x 50 . "\n";
print "  服务: $BASE_URL\n\n";

# 健康检查
my $health_url = "$BASE_URL/health";
my $health_resp = $ua->get($health_url);

if ($health_resp->is_success) {
    my $health = decode_json($health_resp->decoded_content);
    print "  ✅ 状态: $health->{status}\n";
} else {
    print "  ❌ 服务不可用\n";
    exit 1;
}

# 舰船数据
my $ships_url = "$BASE_URL/api/ships";
my $ships_resp = $ua->get($ships_url);

if ($ships_resp->is_success) {
    my $data = decode_json($ships_resp->decoded_content);
    my $ships = $data->{ships} || [];
    my $count = $data->{count} || scalar(@$ships);
    print "  🚀 舰船总数: $count 艘\n\n";

    # 按类型统计
    my %type_count;
    foreach my $ship (@$ships) {
        my $type = $ship->{type} || 'unknown';
        $type_count{$type}++;
    }

    my %type_names = (
        battleship => '战列舰',      battlecruiser => '战巡',
        aircraftcarrier => '航母',    support => '支援舰',
        cruiser => '巡洋舰',          destroyer => '驱逐舰',
        frigate => '护卫舰',          fighter => '战机',
        corvette => '护航艇',
    );

    print "  类型分布:\n";
    foreach my $type (sort keys %type_count) {
        my $name = $type_names{$type} || $type;
        printf "    %-10s %3d 艘\n", $name, $type_count{$type};
    }
}

print "\n" . "=" x 50 . "\n";
