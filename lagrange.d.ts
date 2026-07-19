/**
 * ============================================================
 * 拉格朗日AI — TypeScript 类型定义
 * 为舰船数据库和战斗系统提供完整类型支持
 * 可用于前端 TS/JS 项目的类型检查
 * ============================================================
 */

/** 舰船类型枚举 */
export type ShipType =
  | 'battleship'       // 战列舰
  | 'battlecruiser'    // 战列巡洋舰
  | 'aircraftcarrier'  // 航空母舰
  | 'support'          // 支援舰
  | 'cruiser'          // 巡洋舰
  | 'destroyer'        // 驱逐舰
  | 'frigate'          // 护卫舰
  | 'fighter'          // 战机
  | 'corvette';        // 护航艇

/** 舰船大小 */
export type ShipSize = 'large' | 'small' | 'aircraft';

/** 舰船位置 */
export type ShipPosition = 'front' | 'mid' | 'back' | 'air';

/** 评级等级 */
export type Rating = 'S' | 'A' | 'B' | 'C' | 'D';

/** 伤害类型 */
export type DamageType = 'physical' | 'energy';

/** 武器类型 */
export type WeaponType = 'direct' | 'projectile';

/** 战斗模式 */
export type BattleMode = 'escort' | 'bomb';

/** 舰载机模式 */
export type AircraftMode = 'independent' | 'reciprocating';

/** 防空类型 */
export type AAType = 'counter' | 'area' | 'active';

/** 系统类型 */
export type SystemType = 'main_weapon' | 'hangar' | 'command' | 'propulsion';

/** 舰船评级对象 */
export interface ShipRatings {
  antiShip: Rating;   // 对舰
  antiAir: Rating;    // 防空
  siege: Rating;      // 攻城
  survival: Rating;   // 生存
  strategy: Rating;   // 战略
}

/** 舰船速度 */
export interface ShipSpeed {
  cruise: number;  // 巡航速度
  warp: number;    // 曲率速度
}

/** 舰载机槽位 */
export interface AircraftSlots {
  fighter: number;   // 战机槽位
  corvette: number;  // 护航艇槽位
}

/** 武器定义 */
export interface WeaponDef {
  name: string;
  dmgType: DamageType;
  weaponType: WeaponType;
  singleDmg: number;
  ammo: number;
  attacks: number;
  atkDuration: number;
  lockTime: number;
  cooldown: number;
  priority: string;
  crit: boolean;
  lockEfficiency: number;
  dpm?: {
    antiShip: number;
    antiAir: number;
    siege: number;
    repair: number;
  };
  targets?: Array<{
    types: string[];
    hitMin: number;
    hitMax: number;
  }>;
  strategies?: Array<{
    name: string;
    effect: string;
  }>;
  antiAirType?: AAType;
  interceptRate?: number;
}

/** 模块变体 */
export interface ModuleVariant {
  name: string;
  type?: string;
  effect?: string;
}

/** 舰船模块 */
export interface ShipModule {
  name: string;
  type: 'weapon' | 'system' | 'armor' | 'engine' | 'support' | 'moduleGroup';
  selfRepair?: boolean;
  weapons?: WeaponDef[];
  variants?: Record<string, ModuleVariant>;
  current?: string;
  antiAirType?: string;
  interceptRate?: number;
}

/** 完整舰船数据 */
export interface ShipData {
  id: string;
  name: string;
  variant: string;
  type: ShipType;
  size: ShipSize;
  position: ShipPosition;
  hp: number;
  physicalArmor: number;
  energyArmor: number;
  commandValue: number;
  serviceLimit: number;
  speed: ShipSpeed;
  ratings: ShipRatings;
  isCarrier?: boolean;
  aircraftSlots?: AircraftSlots;
  aircraftType?: ShipType;
  squadronSize?: number;
  modules?: Record<string, ShipModule>;
}

/** 舰队槽位 */
export interface FleetSlot {
  main: ShipData[];          // 主力舰队
  reinforcement: ShipData[];  // 增援舰队
  flagship: string | null;   // 旗舰ID
}

/** 舰队配置 */
export interface FleetConfig {
  'ally-escort': FleetSlot;
  'ally-escorted': FleetSlot;
  'enemy-escort': FleetSlot;
  'enemy-escorted': FleetSlot;
  'bomb-fleet': FleetSlot;
}

/** 战斗状态 */
export interface BattleState {
  allyShips: ShipInstance[];
  enemyShips: ShipInstance[];
  time: number;
  ended: boolean;
  winner: string;
  logs: string[];
  mode: BattleMode;
  allyEscortAlive: boolean;
  enemyEscortAlive: boolean;
  totalAllyDamage: number;
  totalEnemyDamage: number;
  allyShipsLost: number;
  enemyShipsLost: number;
}

/** 舰船战斗实例 */
export interface ShipInstance extends ShipData {
  side: 'ally' | 'enemy';
  currentHp: number;
  maxHp: number;
  alive: boolean;
  isEscort: boolean;
  isEscorted: boolean;
  weaponStates: WeaponState[];
  subSystems: Record<string, boolean>;
}

/** 武器状态 */
export interface WeaponState {
  weapon: WeaponDef;
  phase: 'cooldown' | 'lock' | 'attack';
  cooldownRemaining: number;
  lockRemaining: number;
  attackRemaining: number;
  shotsFired: number;
  totalShots: number;
  currentTarget: ShipInstance | null;
}

/** API 响应 */
export interface APIResponse<T> {
  success: boolean;
  message: string;
  data?: T;
}

export interface ShipsResponse {
  ships: ShipData[];
  count: number;
  source: string;
}

export interface ChatResponse {
  answer: string;
  source_docs: Array<{ file_name: string; snippet: string }>;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  platform_tokens_remaining: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
  platform_tokens: number;
}

/** 全局状态 */
export interface AppState {
  token: string;
  user: { username: string; platform_tokens: number } | null;
  ships: ShipData[];
  fleets: FleetConfig;
  currentFleetKey: keyof FleetConfig;
  chatHistory: ChatMessage[];
  battleState: BattleState | null;
  shipCategoryFilter: string;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  sourceDocs?: Array<{ file_name: string; snippet: string }>;
  tokens?: number;
}
