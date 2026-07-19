(* ============================================================
   拉格朗日AI — Pascal 程序：舰船统计
   编译：fpc ship_stats.pas
   ============================================================ *)

program ShipStats;

uses
  SysUtils, Classes;

type
  TShipRecord = record
    Name: string;
    ShipType: string;
    HP: Int64;
    CommandValue: Integer;
  end;

const
  MAX_SHIPS = 200;

var
  Ships: array[1..MAX_SHIPS] of TShipRecord;
  ShipCount: Integer;
  TotalHP: Int64;
  AvgHP: Real;
  i: Integer;

{ 初始化内置舰船数据 }
procedure InitShips;
begin
  ShipCount := 9;
  
  Ships[1].Name := '永恒风暴级'; Ships[1].ShipType := '战巡'; Ships[1].HP := 320000; Ships[1].CommandValue := 40;
  Ships[2].Name := '普卢托斯之盾级'; Ships[2].ShipType := '战巡'; Ships[2].HP := 350000; Ships[2].CommandValue := 42;
  Ships[3].Name := 'CV3000级'; Ships[3].ShipType := '航母'; Ships[3].HP := 240000; Ships[3].CommandValue := 35;
  Ships[4].Name := '光追级'; Ships[4].ShipType := '巡洋舰'; Ships[4].HP := 85000; Ships[4].CommandValue := 18;
  Ships[5].Name := '卡利斯托级'; Ships[5].ShipType := '巡洋舰'; Ships[5].HP := 78000; Ships[5].CommandValue := 16;
  Ships[6].Name := '爱奥级'; Ships[6].ShipType := '巡洋舰'; Ships[6].HP := 95000; Ships[6].CommandValue := 20;
  Ships[7].Name := '阋神星重炮级'; Ships[7].ShipType := '驱逐舰'; Ships[7].HP := 28000; Ships[7].CommandValue := 8;
  Ships[8].Name := '卡利莱恩级'; Ships[8].ShipType := '护卫舰'; Ships[8].HP := 12000; Ships[8].CommandValue := 4;
  Ships[9].Name := '米斯特拉'; Ships[9].ShipType := '战机'; Ships[9].HP := 2500; Ships[9].CommandValue := 2;
end;

{ 计算统计数据 }
procedure CalculateStats;
begin
  TotalHP := 0;
  for i := 1 to ShipCount do
    TotalHP := TotalHP + Ships[i].HP;
  AvgHP := TotalHP / ShipCount;
end;

{ 输出报告 }
procedure PrintReport;
begin
  WriteLn('========================================');
  WriteLn('  拉格朗日AI — Pascal 舰船统计');
  WriteLn('========================================');
  WriteLn;
  WriteLn('  舰船总数: ', ShipCount, ' 艘');
  WriteLn('  总HP:     ', TotalHP);
  WriteLn('  平均HP:   ', AvgHP:0:0);
  WriteLn;
  WriteLn('  详细列表:');
  WriteLn('  ---------------------------------------');
  
  for i := 1 to ShipCount do
  begin
    Write('  ', Ships[i].Name:20);
    Write(' [', Ships[i].ShipType:8, ']');
    WriteLn(' HP:', Ships[i].HP:10, ' CV:', Ships[i].CommandValue:3);
  end;
  
  WriteLn;
  WriteLn('========================================');
end;

begin
  InitShips;
  CalculateStats;
  PrintReport;
end.
