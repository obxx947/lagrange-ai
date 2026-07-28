<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ship Card - ${ship.name}</title>
    <style>
        :root {
            --bg: #0a0e1a;
            --card-bg: #131829;
            --border: #1e3a8a;
            --text: #d0d8f0;
            --accent: #60a5fa;
            --gold: #f59e0b;
            --red: #ef4444;
            --green: #22c55e;
            --blue: #3b82f6;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: var(--bg);
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            padding: 30px;
            color: var(--text);
        }
        .ship-card {
            max-width: 420px;
            margin: 0 auto;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .card-header {
            background: linear-gradient(135deg, #1a2450 0%, #0f1730 100%);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid var(--border);
        }
        .card-header .ship-tier {
            display: inline-block;
            background: var(--gold);
            color: #000;
            font-size: 10px;
            font-weight: bold;
            padding: 3px 10px;
            border-radius: 12px;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .card-header h2 {
            font-size: 22px;
            color: #fff;
            letter-spacing: 1px;
        }
        .card-header .ship-class {
            font-size: 11px;
            color: #93c5fd;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .card-body { padding: 18px; }

        /* Stat rows */
        .stat-row {
            display: flex;
            align-items: center;
            margin: 8px 0;
            padding: 8px 10px;
            background: #0f172a;
            border-radius: 6px;
        }
        .stat-icon {
            width: 20px;
            height: 20px;
            margin-right: 10px;
            flex-shrink: 0;
            background: var(--border);
            border-radius: 4px;
        }
        .stat-label { flex: 2; font-size: 12px; color: #93c5fd; }
        .stat-value { flex: 1; font-size: 15px; font-weight: bold; text-align: right; }
        .stat-bar {
            flex: 3;
            height: 8px;
            background: #1e293b;
            border-radius: 4px;
            overflow: hidden;
        }
        .stat-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        .stat-bar-fill.hp     { background: var(--green); }
        .stat-bar-fill.armor  { background: var(--blue); }
        .stat-bar-fill.shield { background: #8b5cf6; }
        .stat-bar-fill.speed  { background: var(--gold); }

        /* Weapons section */
        .weapons-section {
            margin-top: 15px;
            border-top: 1px solid #1e293b;
            padding-top: 12px;
        }
        .weapons-section h4 {
            color: var(--accent);
            font-size: 13px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .weapon-row {
            display: flex;
            align-items: center;
            padding: 6px 10px;
            margin: 4px 0;
            background: #0f172a;
            border-radius: 4px;
            font-size: 12px;
        }
        .weapon-name { flex: 3; }
        .weapon-type {
            font-size: 10px;
            background: var(--border);
            color: var(--accent);
            padding: 2px 8px;
            border-radius: 10px;
            margin-right: 8px;
        }
        .weapon-dmg { flex: 1; text-align: right; color: var(--red); }
        .weapon-range { flex: 1; text-align: right; color: var(--gold); }

        /* Rating stars */
        .rating-stars {
            text-align: center;
            margin: 15px 0;
        }
        .rating-stars .star {
            color: var(--gold);
            font-size: 18px;
            margin: 0 2px;
        }
        .rating-stars .star.empty { color: #374151; }

        /* Raw stats grid */
        .raw-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            margin-top: 12px;
        }
        .raw-stat {
            background: #0f172a;
            padding: 8px;
            border-radius: 4px;
            text-align: center;
        }
        .raw-stat .raw-label { font-size: 9px; color: #64748b; text-transform: uppercase; }
        .raw-stat .raw-value { font-size: 14px; font-weight: bold; color: #f0f9ff; }
    </style>
</head>
<body>

<div class="ship-card">
    <!-- Card Header -->
    <div class="card-header">
        <div class="ship-tier">${ship.tier | 'T' + str(ship.tier) if ship.tier else 'T1'}</div>
        <h2>${ship.name}</h2>
        <div class="ship-class">${ship.ship_class | 'Battle Cruiser'}</div>
    </div>

    <!-- Card Body -->
    <div class="card-body">
        <!-- Star Rating -->
        <div class="rating-stars">
            % for i in range(5):
                <span class="star ${'empty' if i >= ship.rating else ''}">&#9733;</span>
            % endfor
        </div>

        <!-- HP Bar -->
        <div class="stat-row">
            <div class="stat-icon"></div>
            <div class="stat-label">Hull Points</div>
            <div class="stat-value">${ship.hp | '{:,}'}</div>
            <div class="stat-bar">
                <div class="stat-bar-fill hp" style="width: ${ship.hp / 100000 * 100}%;"></div>
            </div>
        </div>

        <!-- Armor Bar -->
        <div class="stat-row">
            <div class="stat-icon"></div>
            <div class="stat-label">Armor</div>
            <div class="stat-value">${ship.armor | '{:,}'}</div>
            <div class="stat-bar">
                <div class="stat-bar-fill armor" style="width: ${ship.armor / 50000 * 100}%;"></div>
            </div>
        </div>

        <!-- Shield Bar -->
        <div class="stat-row">
            <div class="stat-icon"></div>
            <div class="stat-label">Shield</div>
            <div class="stat-value">${ship.shield | '{:,}'}</div>
            <div class="stat-bar">
                <div class="stat-bar-fill shield" style="width: ${ship.shield / 80000 * 100}%;"></div>
            </div>
        </div>

        <!-- Speed Bar -->
        <div class="stat-row">
            <div class="stat-icon"></div>
            <div class="stat-label">Speed</div>
            <div class="stat-value">${ship.speed | '{:,.0f}'}</div>
            <div class="stat-bar">
                <div class="stat-bar-fill speed" style="width: ${ship.speed / 1000 * 100}%;"></div>
            </div>
        </div>

        <!-- Raw Stats -->
        <div class="raw-stats">
            <div class="raw-stat">
                <div class="raw-label">Energy</div>
                <div class="raw-value">${ship.energy | '{:,}'}</div>
            </div>
            <div class="raw-stat">
                <div class="raw-label">Evasion</div>
                <div class="raw-value">${ship.evasion | '{:,.1f}'}%</div>
            </div>
            <div class="raw-stat">
                <div class="raw-label">Accuracy</div>
                <div class="raw-value">${ship.accuracy | '{:,.1f}'}%</div>
            </div>
            <div class="raw-stat">
                <div class="raw-label">Crit Rate</div>
                <div class="raw-value">${ship.crit_rate | '{:,.1f}'}%</div>
            </div>
            <div class="raw-stat">
                <div class="raw-label">Crit DMG</div>
                <div class="raw-value">${ship.crit_dmg | '{:,.0f}'}%</div>
            </div>
            <div class="raw-stat">
                <div class="raw-label">Cargo</div>
                <div class="raw-value">${ship.cargo | '{:,}'}</div>
            </div>
        </div>

        <!-- Weapons Section -->
        <div class="weapons-section">
            <h4>Weapon Systems</h4>
            % for weapon in ship.weapons:
            <div class="weapon-row">
                <span class="weapon-type">${weapon.type | 'ENERGY'}</span>
                <span class="weapon-name">${weapon.name}</span>
                <span class="weapon-dmg">${weapon.damage | '{:,}'} DPS</span>
                <span class="weapon-range">${weapon.range | '{:,}'}m</span>
            </div>
            % endfor
        </div>

        <!-- Special Abilities -->
        % if hasattr(ship, 'abilities') and ship.abilities:
        <div class="weapons-section">
            <h4>Special Abilities</h4>
            % for ability in ship.abilities:
            <div style="padding: 6px 10px; margin: 4px 0; background: #1a1040; border-radius: 4px; font-size: 11px;">
                <strong style="color: #8b5cf6;">${ability.name}:</strong>
                <span style="color: #c4b5fd;">${ability.description}</span>
            </div>
            % endfor
        </div>
        % endif
    </div>
</div>

</body>
</html>
