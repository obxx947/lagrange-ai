/**
 * ============================================================
 * 拉格朗日 · 星港指挥中心 — 动态星空背景引擎
 * Canvas 粒子星空 + 流星效果 + 星云渐变
 * ============================================================
 */
(function(){
  'use strict';
  
  const canvas = document.getElementById('starfield');
  if (!canvas) return;
  
  const ctx = canvas.getContext('2d');
  let W, H;
  
  // 星星数组
  const stars = [];
  const STAR_COUNT = 300;
  const shootingStars = [];
  
  // 颜色调色板（深空色调）
  const colors = [
    '#ffffff', '#e8ecf4', '#a0b4cc',
    '#3b8bff', '#6098ff', '#06c8e0',
    '#f0a020', '#9060e0'
  ];
  
  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  
  function createStar() {
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 2 + 0.5,
      color: colors[Math.floor(Math.random() * colors.length)],
      alpha: Math.random() * 0.8 + 0.2,
      twinkleSpeed: Math.random() * 0.02 + 0.005,
      twinkleOffset: Math.random() * Math.PI * 2,
    };
  }
  
  function createShootingStar() {
    const x = Math.random() * W;
    const y = Math.random() * H * 0.5;
    return {
      x, y,
      vx: -(Math.random() * 8 + 4),
      vy: Math.random() * 3 + 1,
      life: 1.0,
      decay: Math.random() * 0.015 + 0.008,
      length: Math.random() * 80 + 40,
    };
  }
  
  function initStars() {
    stars.length = 0;
    for (let i = 0; i < STAR_COUNT; i++) {
      stars.push(createStar());
    }
  }
  
  function drawStars(timestamp) {
    // 清屏（渐变背景）
    const bgGrad = ctx.createRadialGradient(W/2, H/3, 0, W/2, H, Math.max(W,H));
    bgGrad.addColorStop(0, 'rgba(5,12,30,0.95)');
    bgGrad.addColorStop(0.5, 'rgba(3,8,20,0.98)');
    bgGrad.addColorStop(1, 'rgba(1,3,10,0.99)');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);
    
    // 绘制星云光晕
    const nebula1 = ctx.createRadialGradient(W*0.3, H*0.4, 0, W*0.3, H*0.4, W*0.5);
    nebula1.addColorStop(0, 'rgba(59,139,255,0.03)');
    nebula1.addColorStop(1, 'transparent');
    ctx.fillStyle = nebula1;
    ctx.fillRect(0, 0, W, H);
    
    const nebula2 = ctx.createRadialGradient(W*0.7, H*0.3, 0, W*0.7, H*0.3, W*0.4);
    nebula2.addColorStop(0, 'rgba(6,200,224,0.02)');
    nebula2.addColorStop(1, 'transparent');
    ctx.fillStyle = nebula2;
    ctx.fillRect(0, 0, W, H);
    
    // 绘制星星
    for (const star of stars) {
      const twinkle = Math.sin(timestamp * star.twinkleSpeed + star.twinkleOffset) * 0.4 + 0.6;
      const alpha = star.alpha * twinkle;
      
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
      ctx.fillStyle = star.color;
      ctx.globalAlpha = alpha;
      ctx.fill();
      
      // 亮星加光晕
      if (star.r > 1.3 && twinkle > 0.8) {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.r * 3, 0, Math.PI * 2);
        ctx.fillStyle = star.color;
        ctx.globalAlpha = alpha * 0.15;
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    
    // 流星
    for (let i = shootingStars.length - 1; i >= 0; i--) {
      const ss = shootingStars[i];
      ss.x += ss.vx;
      ss.y += ss.vy;
      ss.life -= ss.decay;
      
      if (ss.life <= 0) {
        shootingStars.splice(i, 1);
        continue;
      }
      
      const grad = ctx.createLinearGradient(ss.x, ss.y, ss.x - ss.vx * ss.length, ss.y - ss.vy * ss.length);
      grad.addColorStop(0, `rgba(255,255,255,${ss.life})`);
      grad.addColorStop(1, 'rgba(255,255,255,0)');
      
      ctx.beginPath();
      ctx.moveTo(ss.x, ss.y);
      ctx.lineTo(ss.x - ss.vx * 5, ss.y - ss.vy * 5);
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    
    // 随机生成流星
    if (Math.random() < 0.008 && shootingStars.length < 3) {
      shootingStars.push(createShootingStar());
    }
  }
  
  function animate(timestamp) {
    drawStars(timestamp);
    requestAnimationFrame(animate);
  }
  
  // 导航滚动效果
  function handleScroll() {
    const nav = document.getElementById('topNav');
    if (nav) {
      nav.classList.toggle('scrolled', window.scrollY > 50);
    }
  }
  
  // 平滑滚动
  function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          e.preventDefault();
          target.scrollIntoView({behavior:'smooth',block:'start'});
        }
      });
    });
  }
  
  // 视差效果
  function handleParallax() {
    const ships = document.querySelectorAll('.floating-ship');
    if (!ships.length) return;
    
    const scrollY = window.scrollY;
    ships.forEach((ship, i) => {
      const speed = 0.05 + i * 0.02;
      ship.style.transform = `translateY(${scrollY * speed}px)`;
    });
  }
  
  // 初始化
  window.addEventListener('resize', () => {
    resize();
    initStars();
  });
  window.addEventListener('scroll', () => {
    handleScroll();
    handleParallax();
  });
  
  resize();
  initStars();
  setupSmoothScroll();
  requestAnimationFrame(animate);
  
  console.log('🌌 拉格朗日 · 星港指挥中心 — 星空引擎已启动');
  console.log('   ✨ ' + STAR_COUNT + ' 颗恒星 | ☄ 流星系统 | 🌌 星云光晕');
})();
