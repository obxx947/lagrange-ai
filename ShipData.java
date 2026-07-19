/**
 * ============================================================
 * 拉格朗日AI — Java 类：舰船数据模型
 * 编译：javac -d . ShipData.java
 * 用途：为Android/Java客户端提供舰船数据结构
 * ============================================================
 */

package com.lagrange.ai.model;

import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;

/**
 * 舰船数据模型 — 对应 ship_database.json 的单艘舰船条目
 */
public class ShipData {
    private String id;
    private String name;
    private String variant;
    private String type;
    private String size;
    private String position;
    private long hp;
    private int physicalArmor;
    private int energyArmor;
    private int commandValue;
    private int serviceLimit;
    private Map<String, Integer> speed;
    private Map<String, String> ratings;
    private boolean isCarrier;
    private Map<String, Integer> aircraftSlots;

    // 舰船类型常量
    public static final String TYPE_BATTLESHIP = "battleship";
    public static final String TYPE_BATTLECRUISER = "battlecruiser";
    public static final String TYPE_CARRIER = "aircraftcarrier";
    public static final String TYPE_CRUISER = "cruiser";
    public static final String TYPE_DESTROYER = "destroyer";
    public static final String TYPE_FRIGATE = "frigate";
    public static final String TYPE_FIGHTER = "fighter";
    public static final String TYPE_CORVETTE = "corvette";

    // 评级分数映射
    private static final Map<String, Integer> RATING_SCORES = new HashMap<>();
    static {
        RATING_SCORES.put("S", 10);
        RATING_SCORES.put("A", 7);
        RATING_SCORES.put("B", 4);
        RATING_SCORES.put("C", 2);
        RATING_SCORES.put("D", 0);
    }

    public ShipData() {
        this.speed = new HashMap<>();
        this.ratings = new HashMap<>();
        this.aircraftSlots = new HashMap<>();
    }

    /** 计算舰船综合战斗力评分 */
    public double calculateCombatScore() {
        double hpScore = hp / 10000.0 * 3;
        double armorScore = physicalArmor / 20.0 * 2;
        double shieldScore = energyArmor / 10.0;

        double ratingScore = 0;
        for (String r : ratings.values()) {
            ratingScore += RATING_SCORES.getOrDefault(r, 0);
        }

        double efficiency = hp / (double) Math.max(commandValue, 1) / 1000.0 * 5;
        return hpScore + armorScore + shieldScore + ratingScore + efficiency;
    }

    /** 获取中文类型名称 */
    public String getTypeNameInChinese() {
        Map<String, String> names = new HashMap<>();
        names.put("battleship", "战列舰");
        names.put("battlecruiser", "战列巡洋舰");
        names.put("aircraftcarrier", "航空母舰");
        names.put("support", "支援舰");
        names.put("cruiser", "巡洋舰");
        names.put("destroyer", "驱逐舰");
        names.put("frigate", "护卫舰");
        names.put("fighter", "战机");
        names.put("corvette", "护航艇");
        return names.getOrDefault(type, type);
    }

    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getType() { return type; }
    public void setType(String type) { this.type = type; }
    public long getHp() { return hp; }
    public void setHp(long hp) { this.hp = hp; }
    public int getCommandValue() { return commandValue; }
    public void setCommandValue(int cv) { this.commandValue = cv; }
    public Map<String, String> getRatings() { return ratings; }
    public void setRatings(Map<String, String> ratings) { this.ratings = ratings; }

    @Override
    public String toString() {
        return String.format("[%s] %s | HP:%,d | CV:%d | Score:%.1f",
            getTypeNameInChinese(), name, hp, commandValue, calculateCombatScore());
    }
}
