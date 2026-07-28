// engine_glow.glsl - 拉格朗日舰船引擎辉光着色器
// WebGL片段着色器，用于渲染战舰引擎的辉光效果
// 包含噪声函数、菲涅尔效果和时间动画

precision highp float;

// 统一变量
uniform float uTime;           // 时间 (秒)
uniform vec2 uResolution;      // 分辨率
uniform vec3 uEngineColor;     // 引擎主色 (默认: 0.0, 0.8, 1.0)
uniform float uIntensity;      // 辉光强度 (默认: 1.0)
uniform float uFlickerSpeed;   // 闪烁速度 (默认: 3.0)
uniform float uCoreHeat;       // 核心热量 (0-1, 默认: 0.7)

// 输出
out vec4 fragColor;

// ---- 噪声函数 ----
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
        mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
        f.y
    );
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    for (int i = 0; i < 5; i++) {
        value += amplitude * noise(p * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

// ---- 主函数 ----
void main() {
    // 归一化坐标（中心为原点）
    vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / min(uResolution.x, uResolution.y);

    // 距离中心的径向距离
    float dist = length(uv);

    // 引擎核心（内部明亮区域）
    float core = exp(-dist * 8.0) * uCoreHeat;

    // 外层辉光
    float glow = exp(-dist * 3.0) * 0.5;

    // 噪声扰动（模拟火焰不规则性）
    float flicker = fbm(uv * 12.0 + uTime * uFlickerSpeed) * 0.3;
    flicker += fbm(uv * 6.0 - uTime * 2.0) * 0.5;

    // 菲涅尔效果（边缘更亮）
    float fresnel = pow(dist * 1.5, 2.0);

    // 合成最终颜色
    float alpha = (core + glow) * uIntensity;
    alpha += flicker * 0.2;
    alpha *= 1.0 - fresnel * 0.5;

    // 颜色：内核白色 → 中层青色 → 外层深蓝
    vec3 innerColor = vec3(1.0, 1.0, 1.0);        // 白色内核
    vec3 midColor = uEngineColor;                   // 青色主色
    vec3 outerColor = uEngineColor * 0.3;           // 深蓝外缘

    vec3 color = mix(outerColor, midColor, glow);
    color = mix(color, innerColor, core * 1.5);

    // 温度变化（噪声影响色温）
    float heatShift = fbm(uv * 4.0 + uTime * 0.5) * 0.3;
    color.r += heatShift;
    color.b -= heatShift * 0.5;

    // 脉冲效果
    float pulse = sin(uTime * 8.0) * 0.1 + 0.9;
    alpha *= pulse;

    fragColor = vec4(color, clamp(alpha, 0.0, 1.0));
}
