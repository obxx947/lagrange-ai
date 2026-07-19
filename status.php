<?php
/**
 * ============================================================
 * 拉格朗日AI — PHP API 代理/状态页
 * 提供简单的 PHP 状态检查页面
 * 用法: php -S 0.0.0.0:8080 status.php
 * 访问: http://127.0.0.1:8080/status.php
 * ============================================================
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

$apiBase = 'http://127.0.0.1:3000';
$action = $_GET['action'] ?? 'status';

function callAPI($url) {
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 5);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return ['code' => $httpCode, 'body' => $response];
}

function getShipCount($apiBase) {
    $result = callAPI("$apiBase/api/ships");
    if ($result['code'] === 200) {
        $data = json_decode($result['body'], true);
        return $data['count'] ?? 0;
    }
    return 0;
}

switch ($action) {
    case 'health':
        $result = callAPI("$apiBase/health");
        echo $result['body'];
        break;
        
    case 'stats':
        $health = callAPI("$apiBase/health");
        $healthData = json_decode($health['body'], true);
        
        echo json_encode([
            'status' => $health['code'] === 200 ? 'ok' : 'down',
            'server_time' => date('Y-m-d H:i:s'),
            'php_version' => PHP_VERSION,
            'api_health' => $healthData,
            'ships' => getShipCount($apiBase),
            'api_base' => $apiBase,
        ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        break;
        
    case 'info':
        phpinfo();
        break;
        
    default:
        echo json_encode([
            'name' => '拉格朗日AI — PHP状态代理',
            'version' => '2.0.0',
            'endpoints' => [
                '?action=health' => 'API健康检查',
                '?action=stats' => '系统统计',
                '?action=info' => 'PHP信息',
            ],
        ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
}
