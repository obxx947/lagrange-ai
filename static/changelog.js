/* ========================================
   更新记录组件（changelog）
   - 记录每一次更新（时间+内容）
   - 用户可随时查看、可自行添加需求/记录（localStorage）
   - 支持导出JSON（方便把需求发给开发者）
   轻量：一个模态框，不干扰主流程
   ======================================== */

(function(){
    // ======== 项目更新记录（时间+内容，最新在上） ========
    const CHANGELOG = [
        {time:'2026-08-08', content:'🔒 质检强制工作流程上线：舰船类问题（名称/参数/性能/配置/规格）禁止凭模型固有知识作答→强制检索【舰船数据分类】→逐条比对输出参数→无记载统一回复"该舰船相关参数暂无资料库收录"→冲突以知识库MD为唯一标准答案→输出前自检；未检索直接作答判违规不得PASS。'},
        {time:'2026-08-08', content:'📚 知识库整体替换：与桌面「数据」文件夹完全同步（47个md：战斗机制/舰船基础信息/黑话/实例 + 数据01-07讲解分页 + 舰船数据01-36），旧txt资料已移除；RAG 向量索引已重建（47文件/1697块）。'},
        {time:'2026-08-07', content:'🔧 修复「频繁回复失败」根因：①「更新记录」按钮与发送按钮重叠导致点击发送被遮挡（按钮已移至左下角，不再拦截）；②LLM 调用失败自动重试（最多2次）；③AI 提问卡片保留不被"未收到回复"覆盖，提问计入工具调用上限；④失败时展示具体错误信息。'},
        {time:'2026-08-07', content:'🚢 战斗模拟器舰船补充：新增 25 艘舰船（资料缺失17艘含参数 + 黑话确认8艘基础条目），总数达 193 艘；get_ship_data 可查全部新增舰船。'},
        {time:'2026-08-07', content:'📚 知识库精炼：数据文件夹新增「精炼」子目录（166 条舰船结构化数据，去除策略介绍），lagrange_docs/ 已同步并重建 RAG 索引（68文件/2464块）。'},
        {time:'2026-08-07', content:'🔬 质检升级为 FACT-AUDIT 流水线（主张拆解→证据检索→3裁判辩论→五层审计→LLM-as-Judge评分→链状回溯局部修正，FULL_REGEN上限6轮）；AgentForesight 工具前置预检。'},
        {time:'2026-08-07', content:'🎯 AI 主动提问功能：AI 需求不明确时列出选项（单选/多选）并附自由输入框，等待你的回答后继续；工具调用上限（同工具3次/总20次）。'},
        {time:'2026-08-07', content:'🧮 战斗模拟器对照《战斗机制.txt》全面修正：攻击周期=冷却/锁定并行+攻击持续、逐发护甲/护盾、命中/暴击/分伤机制、拦截累乘、系统自修次数上限。'},
        {time:'2026-08-07', content:'🏗️ 新增知识库开发流水线（kb_pipeline.py）：摄入清洗→语义分块(父子块+标签)→LLM实体抽取(知识图谱)→多裁判冲突仲裁(勘误报告)，产物输出 kb_dev_output/。'},
        {time:'2026-08-07', content:'🔬 质检升级为 FACT-AUDIT 流水线：主张拆解→证据检索→3裁判辩论→五层审计→LLM-as-Judge 0-100评分→链状回溯局部修正，FULL_REGEN重跑上限6轮。'},
        {time:'2026-08-07', content:'📋 本组件上线：随时查看更新记录、添加你的需求（自动带时间，可导出JSON）。'},
    ];

    // ======== 配置 ========
    const CFG = {
        storageKey: 'lagrange_changelog_user',   // 用户本地添加的记录
        project: '拉格朗日智能体',
    };

    // ======== 样式注入 ========
    function injectCSS(){
        if(document.getElementById('changelogCSS')) return;
        const css = `
#changelogBtn{position:fixed;left:14px;bottom:14px;right:auto;z-index:999;background:rgba(22,27,34,.92);border:1px solid #2d333b;color:#9da7b3;border-radius:20px;padding:7px 14px;font-size:12px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.4)}
#changelogBtn:hover{color:#e6edf3;border-color:#6e7681}
#changelogModal{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:1000;display:none;align-items:center;justify-content:center}
#changelogModal.active{display:flex}
#changelogBox{background:#161b22;border:1px solid #2d333b;border-radius:12px;width:min(560px,92vw);max-height:82vh;display:flex;flex-direction:column;box-shadow:0 8px 32px rgba(0,0,0,.5)}
#changelogHead{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid #2d333b}
#changelogHead h3{margin:0;font-size:15px;color:#e6edf3}
#changelogClose{background:none;border:none;color:#9da7b3;font-size:18px;cursor:pointer;padding:2px 8px}
#changelogClose:hover{color:#e6edf3}
#changelogList{flex:1;overflow-y:auto;padding:10px 18px}
#changelogList .cl-item{padding:9px 0;border-bottom:1px dashed #21262d;font-size:13px;line-height:1.7}
#changelogList .cl-item:last-child{border-bottom:none}
#changelogList .cl-time{color:#e3b341;font-size:11px;font-weight:600;margin-bottom:2px}
#changelogList .cl-content{color:#e6edf3}
#changelogList .cl-tag{display:inline-block;font-size:10px;border:1px solid #2d333b;border-radius:4px;padding:0 6px;margin-left:6px;color:#8b949e}
#changelogFoot{border-top:1px solid #2d333b;padding:12px 18px;display:flex;flex-direction:column;gap:8px}
#changelogFoot textarea{width:100%;background:#0d1117;border:1px solid #2d333b;border-radius:8px;color:#e6edf3;padding:8px 10px;font-size:12px;resize:vertical;font-family:inherit}
#changelogFoot .cl-btns{display:flex;gap:8px;align-items:center}
.cl-btn{background:#e3b341;color:#1a1a1a;border:none;border-radius:6px;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer}
.cl-btn.ghost{background:transparent;color:#9da7b3;border:1px solid #2d333b}
.cl-btn:hover{filter:brightness(1.1)}
.cl-btn:disabled{opacity:.5;cursor:not-allowed}
#clTip{font-size:11px;color:#6e7681;margin-left:auto}
`;
        const style = document.createElement('style');
        style.id = 'changelogCSS';
        style.textContent = css;
        document.head.appendChild(style);
    }

    // ======== 数据 ========
    function getUserRecords(){
        try{ return JSON.parse(localStorage.getItem(CFG.storageKey))||[]; }catch(e){ return []; }
    }
    function saveUserRecord(content){
        const recs = getUserRecords();
        const now = new Date();
        const pad = n => String(n).padStart(2,'0');
        recs.unshift({time:`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`, content:String(content).trim(), mine:true});
        localStorage.setItem(CFG.storageKey, JSON.stringify(recs.slice(0,200)));
        return recs;
    }

    // ======== 模态框 ========
    function buildModal(){
        if(document.getElementById('changelogModal')) return;
        const div = document.createElement('div');
        div.id = 'changelogModal';
        div.innerHTML = `
        <div id="changelogBox">
            <div id="changelogHead">
                <h3>📋 更新记录 · ${CFG.project}</h3>
                <button id="changelogClose" title="关闭">✕</button>
            </div>
            <div id="changelogList"></div>
            <div id="changelogFoot">
                <textarea id="changelogInput" rows="2" placeholder="💡 添加你的需求/建议/记录…（自动带当前时间）"></textarea>
                <div class="cl-btns">
                    <button class="cl-btn" id="changelogAdd">＋ 添加记录</button>
                    <button class="cl-btn ghost" id="changelogExport">⬇ 导出JSON</button>
                    <span id="clTip">记录仅保存在本浏览器</span>
                </div>
            </div>
        </div>`;
        document.body.appendChild(div);
        document.getElementById('changelogClose').onclick = close;
        div.addEventListener('click', e=>{ if(e.target===div) close(); });
        document.getElementById('changelogAdd').onclick = ()=>{
            const ta = document.getElementById('changelogInput');
            const v = ta.value.trim();
            if(!v) return;
            saveUserRecord(v);
            ta.value = '';
            renderList();
        };
        document.getElementById('changelogExport').onclick = ()=>{
            const all = [...getUserRecords(), ...CHANGELOG];
            const blob = new Blob([JSON.stringify(all, null, 2)], {type:'application/json;charset=utf-8'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = `${CFG.project}_更新记录.json`;
            document.body.appendChild(a); a.click();
            setTimeout(()=>{ URL.revokeObjectURL(url); a.remove(); }, 1000);
        };
    }

    function renderList(){
        const list = document.getElementById('changelogList');
        const userRecs = getUserRecords();
        const all = [...userRecs, ...CHANGELOG];
        list.innerHTML = all.map(r=>`
            <div class="cl-item">
                <div class="cl-time">${r.time}${r.mine?'<span class="cl-tag">我的记录</span>':''}</div>
                <div class="cl-content">${esc(String(r.content||''))}</div>
            </div>`).join('') || '<div class="cl-item" style="color:#6e7681">暂无记录</div>';
        list.scrollTop = 0;
    }

    function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

    function open(){ injectCSS(); buildModal(); renderList(); document.getElementById('changelogModal').classList.add('active'); }
    function close(){ const m = document.getElementById('changelogModal'); if(m) m.classList.remove('active'); }

    // ======== 入口按钮（右下角悬浮） ========
    function mount(){
        if(document.getElementById('changelogBtn')) return;
        injectCSS();
        const btn = document.createElement('button');
        btn.id = 'changelogBtn';
        btn.textContent = '📋 更新记录';
        btn.title = '查看更新记录 / 添加你的需求';
        btn.onclick = open;
        document.body.appendChild(btn);
    }

    // ======== 聊天栏提醒条（chat.html：输入框上方细提示条，轻量不阻塞） ========
    function mountChatTip(){
        if(document.getElementById('changelogTip')) return;
        if(localStorage.getItem(CFG.storageKey + '_tipClosed')) return;
        const input = document.getElementById('chatInput');
        if(!input) return;
        const area = input.closest('.input-area') || input.parentElement;
        if(!area) return;
        const tip = document.createElement('div');
        tip.id = 'changelogTip';
        tip.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:12px;color:#8b949e;background:rgba(227,179,65,.07);border:1px solid rgba(227,179,65,.22);border-radius:8px;padding:5px 12px;margin-bottom:6px;cursor:pointer;user-select:none';
        tip.innerHTML = '<span>💡 支持随时查看更新记录、添加你的需求</span><span style="color:#e3b341;font-weight:600">📋</span><span class="cl-tip-close" style="margin-left:auto;color:#8b949e;font-size:14px;padding:0 4px" title="关闭提醒">✕</span>';
        tip.addEventListener('click', e=>{
            if(e.target.classList.contains('cl-tip-close')) return;
            open();
        });
        tip.querySelector('.cl-tip-close').addEventListener('click', e=>{
            e.stopPropagation();
            tip.remove();
            localStorage.setItem(CFG.storageKey + '_tipClosed', '1');
        });
        area.insertBefore(tip, area.firstChild);
        // 1分钟后自动淡出，不打扰
        setTimeout(()=>{
            if(document.getElementById('changelogTip')){
                const t = document.getElementById('changelogTip');
                t.style.transition = 'opacity .8s';
                t.style.opacity = '.35';
            }
        }, 60000);
    }

    // ======== 自动挂载（页面加载后） ========
    function autoMount(){
        mount();
        if(document.getElementById('chatInput')) mountChatTip();
    }
    if(document.readyState === 'loading'){
        window.addEventListener('DOMContentLoaded', autoMount);
    } else {
        autoMount();
    }

    window.Changelog = {open, close, mount, mountChatTip, getUserRecords, saveUserRecord};
    window.CHANGELOG = CHANGELOG;
})();
