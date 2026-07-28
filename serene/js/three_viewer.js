/**
 * three_viewer.js - 拉格朗日品牌站 3D舰船展示
 *
 * 使用Three.js在品牌页面展示3D舰船模型。
 * 如果没有实际3D模型文件，使用几何体构建抽象舰船轮廓。
 * 支持鼠标拖拽旋转/缩放，自动旋转展示。
 *
 * 依赖: Three.js (CDN加载)
 * 许可: MIT
 */

(function() {
  'use strict';

  // ==================== 配置 ====================
  const CONFIG = {
    containerId: 'ship-3d-viewer',
    autoRotate: true,
    autoRotateSpeed: 0.3,
    backgroundColor: 0x0a0a1a,
    ambientLightColor: 0x334466,
    ambientLightIntensity: 0.4,
    directionalLightColor: 0x88aaff,
    directionalLightIntensity: 1.2,
    shipColor: 0x4488cc,
    shipSecondaryColor: 0x2255aa,
    shipAccentColor: 0xff6633,
    engineColor: 0x00ccff,
    particlesCount: 200,
    particlesColor: 0x88aaff,
  };

  // ==================== 状态管理 ====================
  let scene, camera, renderer, shipGroup, particles;
  let animationId, isDragging = false;
  let previousMouse = { x: 0, y: 0 };
  let targetRotation = { x: 0, y: 0 };
  let currentRotation = { x: 0.3, y: 0 };

  // ==================== 初始化 ====================
  function init() {
    const container = document.getElementById(CONFIG.containerId);
    if (!container) {
      console.warn('3D viewer container not found:', CONFIG.containerId);
      return;
    }

    // 场景
    scene = new THREE.Scene();
    scene.background = new THREE.Color(CONFIG.backgroundColor);
    scene.fog = new THREE.FogExp2(CONFIG.backgroundColor, 0.0003);

    // 相机
    const aspect = container.clientWidth / container.clientHeight;
    camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
    camera.position.set(0, 2, 12);
    camera.lookAt(0, 0, 0);

    // 渲染器
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);

    // 光照
    setupLights();

    // 舰船模型
    shipGroup = new THREE.Group();
    createAbstractShip(shipGroup);
    scene.add(shipGroup);

    // 粒子背景
    createStarfieldParticles();
    scene.add(particles);

    // 网格参考面
    const gridHelper = new THREE.PolarGridHelper(8, 16, 12, 64, 0x334466, 0x223355);
    gridHelper.position.y = -4;
    scene.add(gridHelper);

    // 事件监听
    setupEventListeners(container);

    // 启动动画循环
    animate();
  }

  // ==================== 光照设置 ====================
  function setupLights() {
    // 环境光
    const ambientLight = new THREE.AmbientLight(
      CONFIG.ambientLightColor,
      CONFIG.ambientLightIntensity
    );
    scene.add(ambientLight);

    // 主方向光（模拟太阳光）
    const mainLight = new THREE.DirectionalLight(
      CONFIG.directionalLightColor,
      CONFIG.directionalLightIntensity
    );
    mainLight.position.set(10, 15, 10);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.width = 1024;
    mainLight.shadow.mapSize.height = 1024;
    mainLight.shadow.camera.near = 1;
    mainLight.shadow.camera.far = 50;
    mainLight.shadow.camera.left = -15;
    mainLight.shadow.camera.right = 15;
    mainLight.shadow.camera.top = 15;
    mainLight.shadow.camera.bottom = -15;
    scene.add(mainLight);

    // 引擎光（蓝色点光源，模拟引擎辉光）
    const engineLight = new THREE.PointLight(CONFIG.engineColor, 2, 8);
    engineLight.position.set(0, -0.5, -4);
    scene.add(engineLight);

    // 补光
    const fillLight = new THREE.DirectionalLight(0x4466aa, 0.3);
    fillLight.position.set(-5, 3, -5);
    scene.add(fillLight);

    // 底部补光
    const rimLight = new THREE.DirectionalLight(0x224488, 0.5);
    rimLight.position.set(0, -3, 5);
    scene.add(rimLight);
  }

  // ==================== 抽象舰船建模 ====================
  function createAbstractShip(group) {
    const matBody = new THREE.MeshStandardMaterial({
      color: CONFIG.shipColor,
      roughness: 0.4,
      metalness: 0.7,
    });
    const matSecondary = new THREE.MeshStandardMaterial({
      color: CONFIG.shipSecondaryColor,
      roughness: 0.3,
      metalness: 0.8,
    });
    const matAccent = new THREE.MeshStandardMaterial({
      color: CONFIG.shipAccentColor,
      roughness: 0.2,
      metalness: 0.9,
      emissive: CONFIG.shipAccentColor,
      emissiveIntensity: 0.3,
    });
    const matEngine = new THREE.MeshStandardMaterial({
      color: CONFIG.engineColor,
      roughness: 0.1,
      metalness: 0.1,
      emissive: CONFIG.engineColor,
      emissiveIntensity: 2,
    });
    const matGlow = new THREE.MeshBasicMaterial({
      color: CONFIG.engineColor,
      transparent: true,
      opacity: 0.6,
    });

    // ---- 主体 (拉伸的八面体) ----
    const bodyGeom = new THREE.CylinderGeometry(0.3, 0.8, 5, 8, 4);
    const body = new THREE.Mesh(bodyGeom, matBody);
    body.rotation.x = Math.PI / 2;
    body.castShadow = true;
    group.add(body);

    // ---- 舰桥 (顶部结构) ----
    const bridgeGeom = new THREE.BoxGeometry(0.6, 0.5, 1.2);
    const bridge = new THREE.Mesh(bridgeGeom, matSecondary);
    bridge.position.set(0, 0.7, 0.3);
    bridge.castShadow = true;
    group.add(bridge);

    // ---- 舰桥天线 ----
    const antennaGeom = new THREE.CylinderGeometry(0.05, 0.08, 0.6, 8);
    const antenna = new THREE.Mesh(antennaGeom, matAccent);
    antenna.position.set(0, 1.1, 0.5);
    group.add(antenna);

    // ---- 引擎舱 (4个) ----
    const enginePositions = [
      [0.4, -0.3, -1.5],
      [-0.4, -0.3, -1.5],
      [0.25, 0.1, -1.8],
      [-0.25, 0.1, -1.8],
    ];
    enginePositions.forEach(([x, y, z]) => {
      const engineGeom = new THREE.CylinderGeometry(0.12, 0.18, 0.8, 8);
      const engine = new THREE.Mesh(engineGeom, matEngine);
      engine.position.set(x, y, z);
      engine.castShadow = true;
      group.add(engine);

      // 引擎火焰
      const flameGeom = new THREE.ConeGeometry(0.15, 0.5, 8);
      const flame = new THREE.Mesh(flameGeom, matGlow);
      flame.position.set(x, y, z - 0.6);
      flame.rotation.x = Math.PI;
      flame.name = 'engineFlame';
      group.add(flame);
    });

    // ---- 侧翼 (左右各一) ----
    const wingShape = new THREE.Shape();
    wingShape.moveTo(0, 0);
    wingShape.lineTo(2, -0.3);
    wingShape.lineTo(1.5, -0.6);
    wingShape.lineTo(0, -0.4);
    wingShape.closePath();
    const wingExtrudeSettings = { steps: 1, depth: 0.15, bevelEnabled: true, bevelThickness: 0.05 };
    const wingGeom = new THREE.ExtrudeGeometry(wingShape, wingExtrudeSettings);

    const leftWing = new THREE.Mesh(wingGeom, matSecondary);
    leftWing.position.set(0.3, 0, 1.2);
    leftWing.rotation.set(0, Math.PI / 2, 0);
    leftWing.castShadow = true;
    group.add(leftWing);

    const rightWing = new THREE.Mesh(wingGeom, matSecondary);
    rightWing.position.set(-0.3, 0, 1.2);
    rightWing.rotation.set(0, -Math.PI / 2, 0);
    rightWing.castShadow = true;
    group.add(rightWing);

    // ---- 武器炮塔 ----
    for (let i = -1; i <= 1; i += 2) {
      const turretGeom = new THREE.CylinderGeometry(0.1, 0.15, 0.3, 8);
      const turret = new THREE.Mesh(turretGeom, matAccent);
      turret.position.set(i * 0.7, 0.3, -0.8);
      group.add(turret);

      const barrelGeom = new THREE.CylinderGeometry(0.04, 0.06, 0.6, 8);
      const barrel = new THREE.Mesh(barrelGeom, matAccent);
      barrel.position.set(i * 0.7, 0.35, -1.1);
      barrel.rotation.x = -Math.PI / 4;
      group.add(barrel);
    }
  }

  // ==================== 星空粒子 ====================
  function createStarfieldParticles() {
    const geometry = new THREE.BufferGeometry();
    const count = CONFIG.particlesCount;
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      // 球形分布
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const radius = 15 + Math.random() * 30;

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      sizes[i] = Math.random() * 3 + 0.5;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    const material = new THREE.PointsMaterial({
      color: CONFIG.particlesColor,
      size: 0.08,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      transparent: true,
      opacity: 0.8,
    });

    particles = new THREE.Points(geometry, material);
  }

  // ==================== 动画循环 ====================
  function animate() {
    animationId = requestAnimationFrame(animate);

    const dt = 0.016; // ~60fps

    // 自动旋转
    if (CONFIG.autoRotate && !isDragging) {
      targetRotation.y += CONFIG.autoRotateSpeed * dt;
    }

    // 平滑过渡
    currentRotation.x += (targetRotation.x - currentRotation.x) * 0.05;
    currentRotation.y += (targetRotation.y - currentRotation.y) * 0.05;

    shipGroup.rotation.y = currentRotation.y;
    shipGroup.rotation.x = currentRotation.x;

    // 引擎火焰动画
    shipGroup.children.forEach(child => {
      if (child.name === 'engineFlame') {
        child.scale.y = 0.8 + Math.sin(Date.now() * 0.01) * 0.3;
        child.material.opacity = 0.4 + Math.sin(Date.now() * 0.015) * 0.2;
      }
    });

    // 粒子旋转
    if (particles) {
      particles.rotation.y += 0.0001;
      particles.rotation.x += 0.00005;
    }

    renderer.render(scene, camera);
  }

  // ==================== 事件处理 ====================
  function setupEventListeners(container) {
    // 鼠标交互
    container.addEventListener('mousedown', (e) => {
      isDragging = true;
      previousMouse.x = e.clientX;
      previousMouse.y = e.clientY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - previousMouse.x;
      const dy = e.clientY - previousMouse.y;
      targetRotation.y += dx * 0.005;
      targetRotation.x += dy * 0.005;
      targetRotation.x = Math.max(-1, Math.min(1.5, targetRotation.x));
      previousMouse.x = e.clientX;
      previousMouse.y = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      isDragging = false;
    });

    // 触摸交互
    container.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        isDragging = true;
        previousMouse.x = e.touches[0].clientX;
        previousMouse.y = e.touches[0].clientY;
      }
    }, { passive: true });

    container.addEventListener('touchmove', (e) => {
      if (!isDragging || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - previousMouse.x;
      const dy = e.touches[0].clientY - previousMouse.y;
      targetRotation.y += dx * 0.005;
      targetRotation.x += dy * 0.005;
      targetRotation.x = Math.max(-1, Math.min(1.5, targetRotation.x));
      previousMouse.x = e.touches[0].clientX;
      previousMouse.y = e.touches[0].clientY;
    }, { passive: true });

    container.addEventListener('touchend', () => {
      isDragging = false;
    });

    // 滚轮缩放
    container.addEventListener('wheel', (e) => {
      e.preventDefault();
      camera.position.z += e.deltaY * 0.01;
      camera.position.z = Math.max(5, Math.min(20, camera.position.z));
    }, { passive: false });

    // 响应式调整
    window.addEventListener('resize', () => {
      const aspect = container.clientWidth / container.clientHeight;
      camera.aspect = aspect;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    });

    // 键盘控制
    window.addEventListener('keydown', (e) => {
      switch (e.key.toLowerCase()) {
        case 'r':
          targetRotation.x = 0.3;
          targetRotation.y = 0;
          camera.position.set(0, 2, 12);
          break;
        case 'f':
          camera.position.z = Math.max(5, camera.position.z - 2);
          break;
        case 'g':
          camera.position.z = Math.min(20, camera.position.z + 2);
          break;
      }
    });
  }

  // ==================== 公共API ====================
  window.LagrangeShipViewer = {
    init,
    resetView: () => {
      targetRotation.x = 0.3;
      targetRotation.y = 0;
      camera.position.set(0, 2, 12);
    },
    setAutoRotate: (enabled) => {
      CONFIG.autoRotate = enabled;
    },
    destroy: () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
      if (renderer) {
        renderer.dispose();
      }
    },
  };

  // 自动初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
