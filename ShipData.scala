/**
 * ============================================================
 * 拉格朗日AI — Scala 舰船数据类
 * 编译：scalac ShipData.scala
 * ============================================================
 */

package com.lagrange.ai.model

import scala.util.Try
import play.api.libs.json._

/** 舰船评级 */
object ShipRating extends Enumeration {
  type ShipRating = Value
  val S = Value(10)
  val A = Value(7)
  val B = Value(4)
  val C = Value(2)
  val D = Value(0)
}

/** 舰船类型 */
object ShipType extends Enumeration {
  type ShipType = Value
  val Battleship, Battlecruiser, AircraftCarrier, Support,
      Cruiser, Destroyer, Frigate, Fighter, Corvette = Value

  def toChinese(t: ShipType): String = t match {
    case Battleship => "战列舰"
    case Battlecruiser => "战列巡洋舰"
    case AircraftCarrier => "航空母舰"
    case Support => "支援舰"
    case Cruiser => "巡洋舰"
    case Destroyer => "驱逐舰"
    case Frigate => "护卫舰"
    case Fighter => "战机"
    case Corvette => "护航艇"
  }
}

/** 舰船数据类 */
case class LagrangeShip(
  id: String,
  name: String,
  variant: String = "",
  shipType: ShipType.Value,
  hp: Long,
  physicalArmor: Int,
  energyArmor: Int,
  commandValue: Int,
  ratings: Map[String, ShipRating.Value] = Map.empty
) {
  lazy val fullName: String = if (variant.isEmpty) name else s"$name$variant"
  lazy val isSuperCapital: Boolean = shipType match {
    case ShipType.Battleship | ShipType.Battlecruiser |
         ShipType.AircraftCarrier | ShipType.Support => true
    case _ => false
  }

  /** 战斗力评分 */
  lazy val combatScore: Double = {
    val hpScore = hp / 10000.0 * 3
    val armorScore = physicalArmor / 20.0 * 2
    val shieldScore = energyArmor / 10.0
    val ratingScore = ratings.values.map(_.id.toDouble).sum
    val efficiency = hp / Math.max(commandValue, 1).toDouble / 1000 * 5
    hpScore + armorScore + shieldScore + ratingScore + efficiency
  }

  override def toString: String =
    f"[${ShipType.toChinese(shipType)}] $fullName | HP:$hp%,d | Score:$combatScore%.1f"
}

/** 舰队配置 */
case class LagrangeFleet(
  name: String,
  ships: List[LagrangeShip],
  flagship: Option[LagrangeShip] = None,
  maxCommandValue: Int = 500
) {
  lazy val totalCV: Int = ships.map(_.commandValue).sum
  lazy val totalHP: Long = ships.map(_.hp).sum
  lazy val isValid: Boolean = totalCV <= maxCommandValue

  /** Top N 评分舰船 */
  def topShips(n: Int): List[LagrangeShip] =
    ships.sortBy(-_.combatScore).take(n)
}

/** 伴生对象 — JSON读取 */
object LagrangeShip {
  implicit val shipReads: Reads[LagrangeShip] = Json.reads[LagrangeShip]
}
