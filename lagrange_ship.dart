/// ============================================================
/// 拉格朗日AI — Dart 数据模型
/// 用途：Flutter/Dart 客户端舰船数据结构
/// ============================================================

/// 舰船类型
enum ShipType {
  battleship,
  battlecruiser,
  aircraftcarrier,
  support,
  cruiser,
  destroyer,
  frigate,
  fighter,
  corvette;

  String get chineseName => switch (this) {
    ShipType.battleship => '战列舰',
    ShipType.battlecruiser => '战列巡洋舰',
    ShipType.aircraftcarrier => '航空母舰',
    ShipType.support => '支援舰',
    ShipType.cruiser => '巡洋舰',
    ShipType.destroyer => '驱逐舰',
    ShipType.frigate => '护卫舰',
    ShipType.fighter => '战机',
    ShipType.corvette => '护航艇',
  };

  bool get isSuperCapital => switch (this) {
    ShipType.battleship || ShipType.battlecruiser ||
    ShipType.aircraftcarrier || ShipType.support => true,
    _ => false,
  };
}

/// 评级
enum ShipRating { S, A, B, C, D }

extension ShipRatingExt on ShipRating {
  int get score => switch (this) {
    ShipRating.S => 10, ShipRating.A => 7,
    ShipRating.B => 4,  ShipRating.C => 2, ShipRating.D => 0,
  };
}

/// 舰船数据模型
class LagrangeShip {
  final String id;
  final String name;
  final String variant;
  final ShipType type;
  final int hp;
  final int physicalArmor;
  final int energyArmor;
  final int commandValue;
  final Map<String, ShipRating> ratings;

  const LagrangeShip({
    required this.id, required this.name, this.variant = '',
    required this.type, required this.hp,
    this.physicalArmor = 0, this.energyArmor = 0,
    this.commandValue = 0, this.ratings = const {},
  });

  String get fullName => variant.isEmpty ? name : '$name$variant';

  /// 战斗评分
  double get combatScore {
    final hpScore = hp / 10000.0 * 3;
    final armorScore = physicalArmor / 20.0 * 2;
    final shieldScore = energyArmor / 10.0;
    final ratingScore = ratings.values.fold<int>(0, (s, r) => s + r.score);
    final efficiency = hp / (commandValue.clamp(1, 999)) / 1000.0 * 5;
    return hpScore + armorScore + shieldScore + ratingScore + efficiency;
  }

  factory LagrangeShip.fromJson(Map<String, dynamic> json) {
    return LagrangeShip(
      id: json['id'] ?? '', name: json['name'] ?? '',
      variant: json['variant'] ?? '',
      type: ShipType.values.firstWhere((t) => t.name == json['type'],
          orElse: () => ShipType.cruiser),
      hp: json['hp'] ?? 0, physicalArmor: json['physicalArmor'] ?? 0,
      energyArmor: json['energyArmor'] ?? 0,
      commandValue: json['commandValue'] ?? 0,
      ratings: (json['ratings'] as Map<String, dynamic>?)?.map(
        (k, v) => MapEntry(k, ShipRating.values.firstWhere(
          (r) => r.name == v, orElse: () => ShipRating.C)),
      ) ?? {},
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id, 'name': name, 'variant': variant,
    'type': type.name, 'hp': hp,
    'physicalArmor': physicalArmor, 'energyArmor': energyArmor,
    'commandValue': commandValue,
    'ratings': ratings.map((k, v) => MapEntry(k, v.name)),
  };

  @override
  String toString() => '[${type.chineseName}] $fullName | HP:$hp | Score:${combatScore.toStringAsFixed(1)}';
}
