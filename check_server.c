/**
 * ============================================================
 * 拉格朗日AI — C 语言工具
 * 编译：gcc -o lagrange_check.exe check_server.c -lws2_32
 * 功能：TCP端口连通性检测
 * ============================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <winsock2.h>
#pragma comment(lib, "ws2_32.lib")

#define DEFAULT_HOST "127.0.0.1"
#define DEFAULT_PORT 3000

/** 检查指定主机和端口是否可达 */
int check_port(const char* host, int port) {
    WSADATA wsa;
    SOCKET sock;
    struct sockaddr_in server;
    int result;

    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        printf("  [错误] WSAStartup 失败\n");
        return 0;
    }

    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == INVALID_SOCKET) {
        printf("  [错误] 创建socket失败\n");
        WSACleanup();
        return 0;
    }

    server.sin_family = AF_INET;
    server.sin_addr.s_addr = inet_addr(host);
    server.sin_port = htons(port);

    /* 设置超时2秒 */
    int timeout = 2000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (char*)&timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (char*)&timeout, sizeof(timeout));

    result = connect(sock, (struct sockaddr*)&server, sizeof(server));
    closesocket(sock);
    WSACleanup();

    return result == 0;
}

int main(int argc, char* argv[]) {
    const char* host = DEFAULT_HOST;
    int port = DEFAULT_PORT;

    if (argc > 1) host = argv[1];
    if (argc > 2) port = atoi(argv[2]);

    printf("========================================\n");
    printf("  拉格朗日AI — C 语言端口检测\n");
    printf("========================================\n");
    printf("  目标: %s:%d\n\n", host, port);

    if (check_port(host, port)) {
        printf("  ✅ 端口 %d 可达！服务运行中\n", port);
        printf("  🌐 访问: http://%s:%d\n", host, port);
    } else {
        printf("  ❌ 端口 %d 不可达！服务未运行\n", port);
        printf("  💡 请先启动服务: python main.py\n");
    }

    printf("\n========================================\n");
    return 0;
}
