/**
 * ============================================================
 * 拉格朗日AI — Kotlin 扩展函数
 * 编译：kotlinc ShipExtensions.kt -include-runtime -d ship_ext.jar
 * 用途：为舰船数据提供Kotlin风格的扩展操作
 * ============================================================
 */

package com.lagrange.ai.extensions

import kotlin.math.max
import kotlin.math.min

/** 舰船评级枚举 */
enum class ShipRating(val score: Int) {
    S(10), A(7), B(4), C(2), D(0);

    companion object {
        fun fromString(s: String): ShipRating =
            entries.find { it.name == s } ?: C
    }
}

/** 舰船类型 */
enum class ShipType(val chineseName: String) {
    BATTLESHIP("战列舰"),
    BATTLECRUISER("战列巡洋舰"),
    AIRCRAFTCARRIER("航空母舰"),
    SUPPORT("支援舰"),
    CRUISER("巡洋舰"),
    DESTROYER("驱逐舰"),
    FRIGATE("护卫舰"),
    FIGHTER("战机"),
    CORVETTE("护航艇");

    companion object {
        fun fromString(s: String): ShipType =
            entries.find { it.name.equals(s, ignoreCase = true) } ?: CRUISER
    }
}

/** 舰船数据类 */
data class LagrangeShip(
    val id: String,
    val name: String,
    val variant: String = "",
    val type: ShipType,
    val hp: Long,
    val physicalArmor: Int,
    val energyArmor: Int,
    val commandValue: Int,
    val ratings: Map<String, ShipRating> = emptyMap()
) {
    val fullName: String get() = if (variant.isNotEmpty()) "$name$variant" else name

    /** 计算战斗评分 */
    val combatScore: Double by lazy {
        val hpScore = hp / 10000.0 * 3
        val armorScore = physicalArmor / 20.0 * 2
        val shieldScore = energyArmor / 10.0
        val ratingScore = ratings.values.sumOf { it.score.toDouble() }
        val efficiency = hp / max(commandValue.toDouble(), 1.0) / 1000 * 5
        hpScore + armorScore + shieldScore + ratingScore + efficiency
    }

    /** 是否是超主力舰 */
    val isSuperCapital: Boolean get() =
        type in listOf(ShipType.BATTLESHIP, ShipType.BATTLECRUISER,
                       ShipType.AIRCRAFTCARRIER, ShipType.SUPPORT)

    /** 获取指定评级 */
    fun getRating(category: String): ShipRating =
        ratings[category] ?: ShipRating.C
}

/** 舰队类 */
data class LagrangeFleet(
    val name: String,
    val ships: List<LagrangeShip>,
    val flagship: LagrangeShip? = null,
    val maxCommandValue: Int = 500
) {
    val totalCV: Int get() = ships.sumOf { it.commandValue }
    val totalHP: Long get() = ships.sumOf { it.hp }
    val averageScore: Double get() = if (ships.isEmpty()) 0.0
        else ships.sumOf { it.combatScore } / ships.size

    fun isValid(): Boolean = totalCV <= maxCommandValue

    /** 按评分排序获取前N艘 */
    fun topShips(n: Int): List<LagrangeShip> =
        ships.sortedByDescending { it.combatScore }.take(n)
}

/** 舰队构建器DSL */
fun fleet(name: String, init: FleetBuilder.() -> Unit): LagrangeFleet {
    val builder = FleetBuilder(name)
    builder.init()
    return builder.build()
}

class FleetBuilder(private val name: String) {
    private val ships = mutableListOf<LagrangeShip>()
    private var flagship: LagrangeShip? = null

    fun ship(ship: LagrangeShip, count: Int = 1) {
        repeat(count) { ships.add(ship) }
    }

    fun flagship(ship: LagrangeShip) {
        this.flagship = ship
        if (!ships.contains(ship)) ships.add(ship)
    }

    fun build() = LagrangeFleet(name, ships, flagship)
}
