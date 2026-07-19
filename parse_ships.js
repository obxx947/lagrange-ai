/**
 * 舰船数据库解析器
 * 从 lglrmax.html 提取完整的 SHIP_DATABASE（138+艘舰船）
 * 输出为 JSON 格式供 Python 后端读取
 * 
 * 用法：node parse_ships.js [输入HTML路径] [输出JSON路径]
 */
const fs = require('fs');
const path = require('path');

const inputFile = process.argv[2] || 'lagrange_docs/lglrmax.html';
const outputFile = process.argv[3] || 'lagrange_docs/ship_database.json';

console.log(`[解析器] 读取: ${inputFile}`);

let html = fs.readFileSync(inputFile, 'utf8');

// 提取 SHIP_DATABASE（可能是对象 {...} 或数组 [...]）
// 先找到 const SHIP_DATABASE = 的位置
const dbStart = html.indexOf('const SHIP_DATABASE');
if (dbStart === -1) {
    console.error('[解析器] 未找到 SHIP_DATABASE 定义');
    process.exit(1);
}

// 找到 = 后的 { 或 [
const eqIdx = html.indexOf('=', dbStart);
const braceIdx = Math.min(
    html.indexOf('{', eqIdx) === -1 ? Infinity : html.indexOf('{', eqIdx),
    html.indexOf('[', eqIdx) === -1 ? Infinity : html.indexOf('[', eqIdx)
);

if (braceIdx === Infinity) {
    console.error('[解析器] 无法定位 SHIP_DATABASE 开始');
    process.exit(1);
}

const openChar = html[braceIdx];
const closeChar = openChar === '{' ? '}' : ']';

// 括号匹配找到结束位置
let depth = 0;
let endIdx = braceIdx;
for (let i = braceIdx; i < html.length; i++) {
    if (html[i] === openChar) depth++;
    else if (html[i] === closeChar) {
        depth--;
        if (depth === 0) {
            endIdx = i + 1;
            break;
        }
    }
}

var jsCode = html.substring(braceIdx, endIdx);
const isObject = openChar === '{';

// 如果是对象，包装为数组（Object.values）
if (isObject) {
    // 保持为对象格式，稍后用 Object.values 提取
    console.log('[解析器] SHIP_DATABASE 是对象格式，将提取所有值');
}

console.log(`[解析器] 提取到 ${jsCode.length} 字符的舰船数据`);

// 清理 JavaScript 语法使其变为合法 JSON
function jsToJson(jsStr) {
    // 1. 处理属性名（无引号的 key）
    jsStr = jsStr.replace(/([{,]\s*)([a-zA-Z_$][\w$]*)\s*:/g, '$1"$2":');
    
    // 2. 处理单引号字符串
    jsStr = jsStr.replace(/'([^'\\]*(\\.[^'\\]*)*)'/g, (m, inner) => {
        return '"' + inner.replace(/"/g, '\\"').replace(/\n/g, '\\n') + '"';
    });
    
    // 3. 移除尾随逗号
    jsStr = jsStr.replace(/,(\s*[}\]])/g, '$1');
    
    // 4. 移除注释
    jsStr = jsStr.replace(/\/\/.*/g, '');
    jsStr = jsStr.replace(/\/\*[\s\S]*?\*\//g, '');
    
    return jsStr;
}

// 尝试直接 eval（更安全的方式）
let ships;
try {
    // 使用 Function 构造器创建沙盒环境
    const evalFn = new Function(`return ${jsCode}`);
    const result = evalFn();
    
    if (isObject) {
        // 对象格式：提取所有值
        ships = Object.values(result);
        console.log(`[解析器] 通过 eval 成功解析对象，提取 ${ships.length} 艘舰船`);
    } else {
        ships = result;
        console.log(`[解析器] 通过 eval 成功解析 ${ships.length} 艘舰船`);
    }
} catch (e) {
    console.log(`[解析器] eval 失败: ${e.message}, 尝试 JSON 解析...`);
    
    // 降级：清理后 JSON.parse
    try {
        const jsonStr = jsToJson(jsCode);
        const result = JSON.parse(jsonStr);
        if (isObject) {
            ships = Object.values(result);
        } else {
            ships = result;
        }
        console.log(`[解析器] 通过 JSON.parse 成功解析 ${ships.length} 艘舰船`);
    } catch (e2) {
        console.error(`[解析器] JSON 解析也失败: ${e2.message}`);
        
        // 最后手段：分段解析
        console.log('[解析器] 尝试分段解析...');
        ships = [];
        const shipCount = (jsCode.match(/\bid\s*:\s*/g) || []).length;
        console.log(`[解析器] 检测到约 ${shipCount} 艘舰船定义`);
    }
}

if (!ships || ships.length === 0) {
    console.error('[解析器] 无法解析任何舰船数据');
    process.exit(1);
}

// 清理数据：移除循环引用和函数
function cleanShipData(ship) {
    const cleaned = {};
    const keepKeys = ['id','name','variant','type','size','position','hp','physicalArmor',
                      'energyArmor','commandValue','serviceLimit','speed','ratings',
                      'isCarrier','aircraftSlots','aircraftType','aircraftSize',
                      'squadronSize','flightMode','baseFlightOut','baseFlightBack'];
    
    for (const key of keepKeys) {
        if (ship[key] !== undefined) {
            cleaned[key] = ship[key];
        }
    }
    
    // 清理 modules（保留结构但移除函数）
    if (ship.modules && typeof ship.modules === 'object') {
        cleaned.modules = {};
        for (const [modKey, mod] of Object.entries(ship.modules)) {
            if (!mod || typeof mod !== 'object') continue;
            const cleanMod = {};
            const modKeepKeys = ['name','type','selfRepair','current','effect',
                                 'antiAirType','interceptRate','interceptType'];
            for (const k of modKeepKeys) {
                if (mod[k] !== undefined) cleanMod[k] = mod[k];
            }
            
            // 武器信息
            if (mod.weapons && Array.isArray(mod.weapons)) {
                cleanMod.weapons = mod.weapons.map(w => {
                    const cw = {};
                    const wKeepKeys = ['name','dmgType','weaponType','singleDmg','ammo',
                                       'attacks','atkDuration','lockTime','cooldown',
                                       'priority','crit','lockEfficiency','interceptRate',
                                       'interceptType','antiAirType','cannotBeIntercepted',
                                       'dpm','targets','subSystemTargets','strategies'];
                    for (const k of wKeepKeys) {
                        if (w[k] !== undefined) cw[k] = w[k];
                    }
                    return cw;
                });
            }
            
            // 变体
            if (mod.variants && typeof mod.variants === 'object') {
                cleanMod.variants = {};
                for (const [vk, vv] of Object.entries(mod.variants)) {
                    if (vv && typeof vv === 'object') {
                        cleanMod.variants[vk] = { name: vv.name, type: vv.type, effect: vv.effect };
                    }
                }
            }
            
            cleaned.modules[modKey] = cleanMod;
        }
    }
    
    return cleaned;
}

// 清理所有舰船数据
const cleanedShips = ships.map(cleanShipData);

// 写入 JSON
fs.writeFileSync(outputFile, JSON.stringify(cleanedShips, null, 2), 'utf8');
console.log(`[解析器] 成功导出 ${cleanedShips.length} 艘舰船到 ${outputFile}`);
console.log(`[解析器] 文件大小: ${(fs.statSync(outputFile).size / 1024).toFixed(1)} KB`);

// 统计信息
const types = {};
cleanedShips.forEach(s => {
    const t = s.type || 'unknown';
    types[t] = (types[t] || 0) + 1;
});
console.log('[解析器] 舰船类型分布:', JSON.stringify(types));
