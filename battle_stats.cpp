/**
 * ============================================================
 * 拉格朗日AI — C++ 工具
 * 编译：g++ -std=c++17 -o battle_stats.exe battle_stats.cpp
 * 功能：读取舰船数据库JSON并输出统计报告
 * ============================================================
 */

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <iomanip>
#include <nlohmann/json.hpp>  // 需要 json.hpp 单头文件

// 如果无nlohmann/json，使用简化版：
#ifdef NO_JSON_LIB
// 简易JSON数字提取
int extractInt(const std::string& json, const std::string& key) {
    size_t pos = json.find("\"" + key + "\"");
    if (pos == std::string::npos) return 0;
    pos = json.find(":", pos);
    if (pos == std::string::npos) return 0;
    // 跳过空白和引号
    while (pos < json.size() && (json[pos] == ':' || json[pos] == ' ' || json[pos] == '"')) pos++;
    return std::atoi(json.c_str() + pos);
}
#endif

struct ShipStats {
    std::string type;
    int count = 0;
    long long totalHP = 0;
    int maxHP = 0;
    std::string maxHPName;
};

int main() {
    std::cout << "========================================\n";
    std::cout << "  拉格朗日AI — C++ 舰船统计\n";
    std::cout << "========================================\n\n";

    // 读取JSON文件
    std::ifstream file("lagrange_docs/ship_database.json");
    if (!file.is_open()) {
        std::cout << "  [提示] 舰船数据库文件未找到\n";
        std::cout << "  请先运行: node parse_ships.js\n\n";
        
        // 显示内置统计
        std::cout << "  内置舰船数据统计:\n";
        std::map<std::string, int> types = {
            {"战列舰", 1}, {"战列巡洋舰", 10}, {"航空母舰", 5},
            {"支援舰", 2}, {"巡洋舰", 42}, {"驱逐舰", 42},
            {"护卫舰", 36}, {"战机", 9}, {"护航艇", 22}
        };
        
        for (const auto& [name, count] : types) {
            std::cout << "    " << std::left << std::setw(16) << name 
                      << std::right << std::setw(4) << count << " 艘\n";
        }
        std::cout << "    " << std::left << std::setw(16) << "总计" 
                  << std::right << std::setw(4) << 169 << " 艘\n";
    } else {
        std::string content((std::istreambuf_iterator<char>(file)),
                            std::istreambuf_iterator<char>());
        file.close();
        std::cout << "  舰船数据库已加载 (" << content.size() << " 字节)\n";
    }

    std::cout << "\n========================================\n";
    return 0;
}
