// ============================================================
// 拉格朗日AI — Objective-C 舰船模型
// 编译：clang -framework Foundation -o ship_model ShipModel.m
// ============================================================

#import <Foundation/Foundation.h>

// 舰船类型枚举
typedef NS_ENUM(NSInteger, LagrangeShipType) {
    LagrangeShipTypeBattleship,
    LagrangeShipTypeBattlecruiser,
    LagrangeShipTypeAircraftCarrier,
    LagrangeShipTypeSupport,
    LagrangeShipTypeCruiser,
    LagrangeShipTypeDestroyer,
    LagrangeShipTypeFrigate,
    LagrangeShipTypeFighter,
    LagrangeShipTypeCorvette
};

// 舰船数据模型
@interface LagrangeShip : NSObject

@property (nonatomic, copy) NSString *shipId;
@property (nonatomic, copy) NSString *name;
@property (nonatomic, copy) NSString *variant;
@property (nonatomic, assign) LagrangeShipType type;
@property (nonatomic, assign) NSInteger hp;
@property (nonatomic, assign) NSInteger physicalArmor;
@property (nonatomic, assign) NSInteger energyArmor;
@property (nonatomic, assign) NSInteger commandValue;
@property (nonatomic, strong) NSDictionary<NSString*, NSString*> *ratings;

- (instancetype)initWithDictionary:(NSDictionary *)dict;
- (NSString *)typeNameInChinese;
- (double)calculateCombatScore;
+ (NSArray<LagrangeShip*> *)loadFromAPI:(NSString *)baseURL;

@end

@implementation LagrangeShip

- (instancetype)initWithDictionary:(NSDictionary *)dict {
    self = [super init];
    if (self) {
        _shipId = dict[@"id"] ?: @"";
        _name = dict[@"name"] ?: @"";
        _variant = dict[@"variant"] ?: @"";
        _hp = [dict[@"hp"] integerValue];
        _physicalArmor = [dict[@"physicalArmor"] integerValue];
        _energyArmor = [dict[@"energyArmor"] integerValue];
        _commandValue = [dict[@"commandValue"] integerValue];
        _ratings = dict[@"ratings"];
        
        NSString *typeStr = dict[@"type"];
        if ([typeStr isEqualToString:@"battleship"]) _type = LagrangeShipTypeBattleship;
        else if ([typeStr isEqualToString:@"battlecruiser"]) _type = LagrangeShipTypeBattlecruiser;
        else if ([typeStr isEqualToString:@"aircraftcarrier"]) _type = LagrangeShipTypeAircraftCarrier;
        else if ([typeStr isEqualToString:@"support"]) _type = LagrangeShipTypeSupport;
        else if ([typeStr isEqualToString:@"cruiser"]) _type = LagrangeShipTypeCruiser;
        else if ([typeStr isEqualToString:@"destroyer"]) _type = LagrangeShipTypeDestroyer;
        else if ([typeStr isEqualToString:@"frigate"]) _type = LagrangeShipTypeFrigate;
        else if ([typeStr isEqualToString:@"fighter"]) _type = LagrangeShipTypeFighter;
        else if ([typeStr isEqualToString:@"corvette"]) _type = LagrangeShipTypeCorvette;
    }
    return self;
}

- (NSString *)typeNameInChinese {
    NSDictionary *names = @{
        @(LagrangeShipTypeBattleship): @"战列舰",
        @(LagrangeShipTypeBattlecruiser): @"战列巡洋舰",
        @(LagrangeShipTypeAircraftCarrier): @"航空母舰",
        @(LagrangeShipTypeSupport): @"支援舰",
        @(LagrangeShipTypeCruiser): @"巡洋舰",
        @(LagrangeShipTypeDestroyer): @"驱逐舰",
        @(LagrangeShipTypeFrigate): @"护卫舰",
        @(LagrangeShipTypeFighter): @"战机",
        @(LagrangeShipTypeCorvette): @"护航艇",
    };
    return names[@(self.type)] ?: @"未知";
}

- (double)calculateCombatScore {
    double hpScore = self.hp / 10000.0 * 3;
    double armorScore = self.physicalArmor / 20.0 * 2;
    double shieldScore = self.energyArmor / 10.0;
    
    NSDictionary *scoreMap = @{@"S":@10, @"A":@7, @"B":@4, @"C":@2, @"D":@0};
    double ratingScore = 0;
    for (NSString *val in self.ratings.allValues) {
        ratingScore += [scoreMap[val] doubleValue];
    }
    double efficiency = self.hp / MAX(self.commandValue, 1.0) / 1000.0 * 5;
    return hpScore + armorScore + shieldScore + ratingScore + efficiency;
}

+ (NSArray<LagrangeShip*> *)loadFromAPI:(NSString *)baseURL {
    NSURL *url = [NSURL URLWithString:[NSString stringWithFormat:@"%@/api/ships", baseURL]];
    NSData *data = [NSData dataWithContentsOfURL:url];
    if (!data) return @[];
    
    NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    NSArray *shipsArray = json[@"ships"];
    NSMutableArray *result = [NSMutableArray array];
    for (NSDictionary *dict in shipsArray) {
        [result addObject:[[LagrangeShip alloc] initWithDictionary:dict]];
    }
    return result;
}

- (NSString *)description {
    return [NSString stringWithFormat:@"[%@] %@ | HP:%ld | Score:%.1f",
            [self typeNameInChinese], self.name, (long)self.hp, [self calculateCombatScore]];
}

@end

// 入口测试
int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSLog(@"========================================");
        NSLog(@"  拉格朗日AI — Objective-C 舰船模型");
        NSLog(@"========================================");
        
        NSDictionary *testDict = @{
            @"id": @"cr_light_chaser", @"name": @"光追级", @"type": @"cruiser",
            @"hp": @85000, @"physicalArmor": @45, @"energyArmor": @10,
            @"commandValue": @18, @"ratings": @{@"antiShip": @"A", @"antiAir": @"A"}
        };
        
        LagrangeShip *ship = [[LagrangeShip alloc] initWithDictionary:testDict];
        NSLog(@"  %@", ship);
        NSLog(@"  战斗力: %.1f", [ship calculateCombatScore]);
        NSLog(@"\n========================================");
    }
    return 0;
}
