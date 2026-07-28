/* 浮动按钮 — 跳转到AI对话页 */
(function(){
    const btn = document.createElement('a');
    btn.href = '/chat';
    btn.title = 'AI战术顾问';
    btn.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:999;width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#4a9eff,#00d4ff);border:none;color:#000;font-size:1.3rem;cursor:pointer;box-shadow:0 4px 20px rgba(74,158,255,0.4);transition:all 0.3s;display:flex;align-items:center;justify-content:center;text-decoration:none';
    btn.textContent = '💬';
    btn.onmouseenter = ()=>btn.style.transform='scale(1.1)';
    btn.onmouseleave = ()=>btn.style.transform='';
    document.addEventListener('DOMContentLoaded', ()=>document.body.appendChild(btn));
})();
