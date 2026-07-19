// ============================================================
// 拉格朗日AI — Swift 数据模型
// 用途：iOS/macOS Swift 客户端舰船数据结构
// ============================================================

import Foundation

/// 舰船评级
enum ShipRating: String, Codable, CaseIterable {
    case S, A, B, C, D
    
    var score: Int {
        switch self {
        case .S: return 10
        case .A: return 7
        case .B: return 4
        case .C: return 2
        case .D: return 0
        }
    }
}

/// 舰船类型
enum ShipType: String, Codable, CaseIterable {
    case battleship, battlecruiser, aircraftcarrier, support
    case cruiser, destroyer, frigate, fighter, corvette
    
    var chineseName: String {
        switch self {
        case .battleship: return "战列舰"
        case .battlecruiser: return "战列巡洋舰"
        case .aircraftcarrier: return "航空母舰"
        case .support: return "支援舰"
        case .cruiser: return "巡洋舰"
        case .destroyer: return "驱逐舰"
        case .frigate: return "护卫舰"
        case .fighter: return "战机"
        case .corvette: return "护航艇"
        }
    }
    
    var isSuperCapital: Bool {
        switch self {
        case .battleship, .battlecruiser, .aircraftcarrier, .support:
            return true
        default:
            return false
        }
    }
}

/// 舰船速度
struct ShipSpeed: Codable {
    let cruise: Int
    let warp: Int
}

/// 舰船数据模型
struct LagrangeShip: Codable, Identifiable {
    let id: String
    let name: String
    let variant: String
    let type: ShipType
    let hp: Int
    let physicalArmor: Int
    let energyArmor: Int
    let commandValue: Int
    let ratings: [String: ShipRating]
    let speed: ShipSpeed?
    
    var fullName: String {
        variant.isEmpty ? name : "\(name)\(variant)"
    }
    
    /// 综合战斗力评分
    var combatScore: Double {
        let hpScore = Double(hp) / 10000.0 * 3
        let armorScore = Double(physicalArmor) / 20.0 * 2
        let shieldScore = Double(energyArmor) / 10.0
        let ratingScore = ratings.values.reduce(0) { $0 + $1.score }
        let efficiency = Double(hp) / max(Double(commandValue), 1) / 1000.0 * 5
        return hpScore + armorScore + shieldScore + Double(ratingScore) + efficiency
    }
    
    // MARK: - API 客户端
    
    /// 从API获取所有舰船
    static func fetchAll(from baseURL: String = "http://127.0.0.1:3000") async throws -> [LagrangeShip] {
        guard let url = URL(string: "\(baseURL)/api/ships") else {
            throw URLError(.badURL)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        struct ShipsResponse: Codable {
            let ships: [LagrangeShip]
            let count: Int
        }
        
        let decoder = JSONDecoder()
        let result = try decoder.decode(ShipsResponse.self, from: data)
        return result.ships
    }
    
    /// 健康检查
    static func healthCheck(baseURL: String = "http://127.0.0.1:3000") async -> Bool {
        guard let url = URL(string: "\(baseURL)/health") else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }
}

// MARK: - 舰队配置

struct LagrangeFleet {
    var name: String
    var ships: [LagrangeShip]
    var flagship: LagrangeShip?
    let maxCommandValue: Int = 500
    
    var totalCV: Int { ships.reduce(0) { $0 + $1.commandValue } }
    var totalHP: Int { ships.reduce(0) { $0 + $1.hp } }
    var isValid: Bool { totalCV <= maxCommandValue }
    
    /// 按评分排序
    var topShips: [LagrangeShip] {
        ships.sorted { $0.combatScore > $1.combatScore }
    }
}
