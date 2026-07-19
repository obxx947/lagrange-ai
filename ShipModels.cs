/// ============================================================
/// 拉格朗日AI — C# 类库
/// 编译：csc /target:library /out:LagrangeLib.dll ShipModels.cs
/// 用途：.NET客户端舰船数据模型
/// ============================================================

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace LagrangeAI.Models
{
    /// <summary>舰船类型枚举</summary>
    public enum ShipType
    {
        [JsonPropertyName("battleship")] Battleship,
        [JsonPropertyName("battlecruiser")] Battlecruiser,
        [JsonPropertyName("aircraftcarrier")] AircraftCarrier,
        [JsonPropertyName("support")] Support,
        [JsonPropertyName("cruiser")] Cruiser,
        [JsonPropertyName("destroyer")] Destroyer,
        [JsonPropertyName("frigate")] Frigate,
        [JsonPropertyName("fighter")] Fighter,
        [JsonPropertyName("corvette")] Corvette
    }

    /// <summary>评级等级</summary>
    public enum Rating { S = 10, A = 7, B = 4, C = 2, D = 0 }

    /// <summary>舰船数据模型</summary>
    public class ShipData
    {
        [JsonPropertyName("id")] public string Id { get; set; } = "";
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        [JsonPropertyName("variant")] public string Variant { get; set; } = "";
        [JsonPropertyName("type")] public string Type { get; set; } = "";
        [JsonPropertyName("hp")] public long Hp { get; set; }
        [JsonPropertyName("physicalArmor")] public int PhysicalArmor { get; set; }
        [JsonPropertyName("energyArmor")] public int EnergyArmor { get; set; }
        [JsonPropertyName("commandValue")] public int CommandValue { get; set; }
        [JsonPropertyName("ratings")] public Dictionary<string, string>? Ratings { get; set; }

        public string FullName => string.IsNullOrEmpty(Variant) ? Name : $"{Name}{Variant}";
        public bool IsSuperCapital => Type is "battleship" or "battlecruiser" or "aircraftcarrier" or "support";

        /// <summary>计算综合战斗力评分</summary>
        public double CalculateCombatScore()
        {
            double hpScore = Hp / 10000.0 * 3;
            double armorScore = PhysicalArmor / 20.0 * 2;
            double shieldScore = EnergyArmor / 10.0;

            double ratingScore = 0;
            if (Ratings != null)
            {
                var scoreMap = new Dictionary<string, int> { {"S",10},{"A",7},{"B",4},{"C",2},{"D",0} };
                foreach (var r in Ratings.Values)
                    ratingScore += scoreMap.GetValueOrDefault(r, 0);
            }

            double efficiency = Hp / Math.Max(CommandValue, 1.0) / 1000.0 * 5;
            return hpScore + armorScore + shieldScore + ratingScore + efficiency;
        }

        public string GetTypeName() => Type switch
        {
            "battleship" => "战列舰",
            "battlecruiser" => "战列巡洋舰",
            "aircraftcarrier" => "航空母舰",
            "support" => "支援舰",
            "cruiser" => "巡洋舰",
            "destroyer" => "驱逐舰",
            "frigate" => "护卫舰",
            "fighter" => "战机",
            "corvette" => "护航艇",
            _ => Type
        };

        public override string ToString() =>
            $"[{GetTypeName()}] {FullName} | HP:{Hp:N0} | CV:{CommandValue} | Score:{CalculateCombatScore():F1}";
    }

    /// <summary>舰队配置</summary>
    public class FleetConfig
    {
        public List<ShipData> MainFleet { get; set; } = new();
        public List<ShipData> Reinforcement { get; set; } = new();
        public string? FlagshipId { get; set; }
        public int MaxCV { get; set; } = 500;

        public int TotalCV => MainFleet.Sum(s => s.CommandValue) + Reinforcement.Sum(s => s.CommandValue);
        public bool IsValid => TotalCV <= MaxCV;
        public long TotalHP => MainFleet.Sum(s => s.Hp) + Reinforcement.Sum(s => s.Hp);
    }

    /// <summary>API客户端（简化版）</summary>
    public class LagrangeApiClient
    {
        private readonly HttpClient _http;
        private readonly string _baseUrl;
        private string? _token;

        public LagrangeApiClient(string baseUrl = "http://127.0.0.1:3000")
        {
            _baseUrl = baseUrl;
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
        }

        public async Task<bool> HealthCheckAsync()
        {
            var resp = await _http.GetAsync($"{_baseUrl}/health");
            return resp.IsSuccessStatusCode;
        }

        public async Task<int> GetShipCountAsync()
        {
            var resp = await _http.GetAsync($"{_baseUrl}/api/ships");
            var json = await resp.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            return doc.RootElement.GetProperty("count").GetInt32();
        }
    }
}
