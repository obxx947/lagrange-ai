%% ============================================================
%% 拉格朗日AI — Erlang 模块
%% 编译：erlc lagrange_health.erl
%% 运行：erl -noshell -s lagrange_health check -s init stop
%% ============================================================

-module(lagrange_health).
-export([check/0, check/1, ship_count/0, ship_count/1]).

%% 默认API地址
-define(DEFAULT_URL, "http://127.0.0.1:3000").

%% 健康检查
check() -> check(?DEFAULT_URL).
check(BaseURL) ->
    io:format("========================================~n"),
    io:format("  拉格朗日AI — Erlang 健康检查~n"),
    io:format("========================================~n"),
    io:format("  目标: ~s~n~n", [BaseURL]),

    case httpc:request(get, {BaseURL ++ "/health", []}, [], []) of
        {ok, {{_, 200, _}, _Headers, Body}} ->
            io:format("  ✅ 服务运行中~n"),
            io:format("  响应: ~s~n", [Body]);
        {ok, {{_, Code, _}, _, _}} ->
            io:format("  ❌ HTTP ~p~n", [Code]);
        {error, Reason} ->
            io:format("  ❌ 连接失败: ~p~n", [Reason]),
            io:format("  💡 请先启动: python main.py~n")
    end,
    io:format("~n========================================~n").

%% 舰船数量查询
ship_count() -> ship_count(?DEFAULT_URL).
ship_count(BaseURL) ->
    case httpc:request(get, {BaseURL ++ "/api/ships", []}, [], []) of
        {ok, {{_, 200, _}, _, Body}} ->
            % 简单解析JSON（Erlang无内置JSON，用正则提取count）
            case re:run(Body, "\"count\":\\s*(\\d+)", [{capture, all_but_first, list}]) of
                {match, [CountStr]} ->
                    Count = list_to_integer(CountStr),
                    io:format("  🚀 舰船总数: ~p 艘~n", [Count]),
                    Count;
                nomatch ->
                    io:format("  ⚠ 无法解析舰船数量~n"),
                    0
            end;
        _ ->
            io:format("  ❌ 无法获取舰船数据~n"),
            0
    end.
