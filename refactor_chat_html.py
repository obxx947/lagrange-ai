# -*- coding: utf-8 -*-
content = open('static/chat.html', 'r', encoding='utf-8').read()

# 1. 添加提问卡片CSS
css_marker = ".msg .src{font-size:0.6rem;color:var(--cyan);margin-top:6px;padding-top:5px;border-top:1px solid rgba(255,255,255,0.06)}"
ask_css = css_marker + """
        /* AI提问卡片 */
        .ask-card{align-self:flex-start;max-width:85%;width:100%;background:rgba(255,215,0,0.05);border:1px solid rgba(255,215,0,0.25);border-left:2px solid var(--gold);border-radius:10px;padding:12px 14px;margin:4px 0;animation:fadeIn 0.25s}
        .ask-card .ask-q{font-size:0.82rem;font-weight:600;color:var(--t1);margin-bottom:8px;line-height:1.5}
        .ask-card .ask-opts{display:flex;flex-direction:column;gap:6px;margin-bottom:8px}
        .ask-card .ask-opt{display:flex;align-items:center;gap:8px;padding:7px 10px;border:1px solid var(--border);border-radius:8px;cursor:pointer;font-size:0.75rem;color:var(--t2);transition:all 0.15s;background:rgba(0,0,0,0.15)}
        .ask-card .ask-opt:hover{border-color:var(--blue);color:var(--t1)}
        .ask-card .ask-opt.selected{border-color:var(--gold);color:var(--gold);background:rgba(255,215,0,0.08)}
        .ask-card .ask-opt .ask-box{width:14px;height:14px;border:1px solid var(--border);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:0.6rem;flex-shrink:0}
        .ask-card .ask-opt.selected .ask-box{background:var(--gold);color:#000;border-color:var(--gold)}
        .ask-card textarea{width:100%;background:rgba(0,0,0,0.3);border:1px solid var(--border);border-radius:8px;color:var(--t1);padding:8px 10px;font-size:0.75rem;resize:vertical;min-height:50px;outline:none;font-family:inherit;box-sizing:border-box}
        .ask-card textarea:focus{border-color:var(--gold)}
        .ask-card .ask-actions{display:flex;gap:8px;margin-top:8px;justify-content:flex-end}
        .ask-card .ask-actions button{padding:6px 16px;border-radius:7px;font-size:0.72rem;font-weight:600;cursor:pointer;border:none;transition:all 0.2s}
        .ask-card .ask-submit{background:linear-gradient(135deg,var(--blue),var(--cyan));color:#000}
        .ask-card .ask-submit:hover{box-shadow:0 0 12px rgba(74,158,255,0.4)}
        .ask-card .ask-skip{background:rgba(255,255,255,0.06);border:1px solid var(--border)!important;color:var(--t2)}
        .ask-card .ask-free-hint{font-size:0.62rem;color:var(--t3);margin-top:6px}
"""
if css_marker in content:
    content = content.replace(css_marker, ask_css, 1)
    print("CSS added")
else:
    print("CSS marker NOT FOUND")

# 2. send() 改造：用 streamChat 替换 fetch+reader 部分
# 定位 send() 中 assistant placeholder 到 finish() 前的部分
start_marker = "    // Assistant placeholder"
end_marker = "    finish();\n}"

new_send_part = '''    // Assistant placeholder
    const assistDiv=renderMsg('assistant','',null,true);
    window._currentAssistEl=assistDiv; // 供思考框插入在其前
    let fullAnswer='';
    let sources=[];

    try{
        const result = await streamChat({
            message: msg,
            history: conv.messages.slice(-30),
            simulator_state: null
        }, assistDiv, conv);

        fullAnswer = result.answer;
        sources = result.sources;

        if(fullAnswer){
            conv.messages.push({role:'assistant',content:fullAnswer,meta:{sources}});
            tokenUsed += fullAnswer.length;
        }else if(!document.getElementById('chatMsgs').contains(assistDiv)){
            // msg was removed by error
        }else{
            assistDiv.innerHTML='<span style="color:var(--t3)">（未收到回复）</span>';
        }
        save();
        updateTokenBar();
        renderConvList();

    }catch(e){
        if(document.getElementById('chatMsgs').contains(assistDiv)) assistDiv.remove();
        renderMsg('error','网络错误: '+e.message);
    }
    finish();
}

// ======== SSE流式对话（含提问交互） ========
async function streamChat(body, assistDiv, conv){
    let fullAnswer='';
    let sources=[];
    const resp=await fetch('/api/agent/chat',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body)
    });
    if(!resp.ok){
        if(assistDiv&&assistDiv.parentNode) assistDiv.remove();
        renderMsg('error','HTTP '+resp.status+': '+(resp.status===400?'请先在设置页配置API Key':'服务异常'));
        return {answer:'', sources:[]};
    }
    const reader=resp.body.getReader();
    const decoder=new TextDecoder();
    let buffer='';
    while(true){
        const{ done,value}=await reader.read();
        if(done) break;
        buffer+=decoder.decode(value,{stream:true});
        const lines=buffer.split('\\n');
        buffer=lines.pop()||'';
        for(const line of lines){
            if(!line.startsWith('data: ')) continue;
            try{
                const evt=JSON.parse(line.slice(6));
                const{event:e,data:d,meta}=evt;

                if(e==='status' && d.includes('检索')){
                    setStatus('busy','🔍 '+d);
                    addStatusLine('🔍',d);
                } else if(e==='status' && d.includes('质检')){
                    setStatus('busy','🔬 '+d);
                    addStatusLine('🔬',d);
                } else if(e==='sub_agent'){
                    setStatus('busy','🤖 子代理运行中');
                    addStatusLine('🤖',d);
                } else if(e==='web_search'){
                    setStatus('busy','🌐 联网搜索');
                    addStatusLine('🌐',d);
                } else if(e==='cache'){
                    setStatus('idle','📊 缓存: '+d);
                    addStatusLine('📊',d);
                    if(meta && meta.hit_rate!==undefined) updateCacheChip(meta.hit_rate);
                } else if(e==='thinking'){
                    addThinkingLine(d);
                } else if(e==='tool_start'){
                    setStatus('busy','🔧 调用: '+meta.tool);
                    addStatusLine('🔧','调用工具: '+meta.tool);
                } else if(e==='tool_result'){
                    addStatusLine('📋','工具结果已返回');
                } else if(e==='qc_pass'){
                    addStatusLine('✅','质检通过');
                } else if(e==='qc_fail'){
                    addStatusLine('⚠️','质检: '+d.substring(0,100));
                } else if(e==='ask_user'){
                    // AI提问：渲染提问卡片（暂停当前流）
                    renderAskCard(d, meta);
                } else if(e==='awaiting_user'){
                    addStatusLine('⏸️', d);
                } else if(e==='answer'){
                    fullAnswer=d;
                    if(meta) sources=meta.sources||[];
                    assistDiv.innerHTML=formatContent(d,sources);
                    collapseAllThinking();
                } else if(e==='error'){
                    addStatusLine('❌',d);
                    if(assistDiv&&assistDiv.parentNode) assistDiv.remove();
                } else if(e==='done'){
                    // complete
                }
            }catch(ex){}
        }
        document.getElementById('chatMsgs').scrollTop=document.getElementById('chatMsgs').scrollHeight;
    }
    return {answer:fullAnswer, sources};
}

// ======== AI提问卡片 ========
function renderAskCard(question, meta){
    const card=document.createElement('div');
    card.className='ask-card';
    card.id='askCard';
    card.dataset.askId=meta.ask_id||'';
    const opts=meta.options||[];
    const qtype=meta.type||'free';
    let optsHtml='';
    if(opts.length){
        optsHtml='<div class="ask-opts">'+opts.map((o,i)=>
            '<div class="ask-opt" data-i="'+i+'" onclick="toggleAskOpt(this,\''+qtype+'\')">'+
            '<span class="ask-box">'+(qtype==='single'?'':'✓')+'</span><span>'+o+'</span></div>').join('')+'</div>';
    }
    card.innerHTML='<div class="ask-q">🤔 '+question+'</div>'+
        optsHtml+
        '<textarea id="askFreeText" rows="2" placeholder="'+(opts.length?'也可以直接说说你的想法/补充条件...':'自由输入你的回答...')+'"></textarea>'+
        '<div class="ask-free-hint">💡 可自由输入任何想法或补充信息</div>'+
        '<div class="ask-actions">'+
        '<button class="ask-skip" onclick="skipAsk()">跳过</button>'+
        '<button class="ask-submit" onclick="submitAsk()">提交</button></div>';
    document.getElementById('chatMsgs').appendChild(card);
    document.getElementById('chatMsgs').scrollTop=document.getElementById('chatMsgs').scrollHeight;
}

function toggleAskOpt(el, qtype){
    if(qtype==='single'){
        document.querySelectorAll('#askCard .ask-opt').forEach(o=>o.classList.remove('selected'));
        el.classList.add('selected');
    }else{
        el.classList.toggle('selected');
    }
}

async function submitAsk(){
    const card=document.getElementById('askCard');
    if(!card) return;
    const askId=card.dataset.askId;
    const selections=[...card.querySelectorAll('.ask-opt.selected')].map(o=>o.textContent.trim());
    const freeText=document.getElementById('askFreeText')?document.getElementById('askFreeText').value.trim():'';
    if(!askId) return;
    const btn=card.querySelector('.ask-submit');
    if(btn) btn.disabled=true;
    const parts=[];
    if(selections.length) parts.push('选择: '+selections.join('、'));
    if(freeText) parts.push('补充: '+freeText);
    renderMsg('user', '📝 '+(parts.join(' | ')||'（跳过）'));
    card.remove();
    const conv=conversations[activeConv];
    if(conv) conv.messages.push({role:'user',content:'📝 '+(parts.join(' | ')||'（跳过）')});
    const assistDiv=renderMsg('assistant','',null,true);
    window._currentAssistEl=assistDiv;
    setStatus('busy','继续处理...');
    try{
        const result=await streamChat({
            message:'',
            history:(conversations[activeConv]||{messages:[]}).messages.slice(-30),
            ask_answer:{ask_id:askId, selections, free_text:freeText}
        }, assistDiv, null);
        if(result.answer){
            const c=conversations[activeConv];
            if(c){ c.messages.push({role:'assistant',content:result.answer,meta:{sources:result.sources}}); tokenUsed+=result.answer.length; save(); renderConvList(); }
        }else if(!document.getElementById('chatMsgs').contains(assistDiv)){
            // removed by error
        }else{
            assistDiv.innerHTML='<span style="color:var(--t3)">（未收到回复）</span>';
        }
        updateTokenBar();
    }catch(e){
        if(document.getElementById('chatMsgs').contains(assistDiv)) assistDiv.remove();
        renderMsg('error','网络错误: '+e.message);
    }
    finish();
}

function skipAsk(){
    const card=document.getElementById('askCard');
    if(!card) return;
    const askId=card.dataset.askId;
    card.remove();
    renderMsg('user','📝 跳过');
    const assistDiv=renderMsg('assistant','',null,true);
    window._currentAssistEl=assistDiv;
    setStatus('busy','继续处理...');
    streamChat({
        message:'',
        history:(conversations[activeConv]||{messages:[]}).messages.slice(-30),
        ask_answer:{ask_id:askId, selections:[], free_text:''}
    }, assistDiv, null).then(result=>{
        if(result.answer){
            const c=conversations[activeConv];
            if(c){ c.messages.push({role:'assistant',content:result.answer,meta:{sources:result.sources}}); tokenUsed+=result.answer.length; save(); renderConvList(); }
        }else if(!document.getElementById('chatMsgs').contains(assistDiv)){
            // removed
        }else{
            assistDiv.innerHTML='<span style="color:var(--t3)">（未收到回复）</span>';
        }
        updateTokenBar();
    }).catch(e=>{
        if(document.getElementById('chatMsgs').contains(assistDiv)) assistDiv.remove();
        renderMsg('error','网络错误: '+e.message);
    }).finally(finish);
}'''

s = content.find(start_marker)
e = content.find(end_marker, s)
if s < 0 or e < 0:
    print("ERROR: send markers not found", s, e)
    raise SystemExit(1)
# end_marker 之后保留 finish() 函数本身，因此只替换到 finish();\n 前
e = content.find("    finish();\n}", s)
content = content[:s] + new_send_part + content[e+len("    finish();\n}"):]
print("send() replaced")

open('static/chat.html', 'w', encoding='utf-8').write(content)
print("chat.html 更新完成")
