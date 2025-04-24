# werewolf_assistant.py

import os
import json
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# —— 页面配置 ——
st.set_page_config(page_title="狼人杀AI助手", page_icon="🎭")

# —— 加载环境变量 ——
load_dotenv()
if not os.getenv("DEESEEK_API_KEY") or not os.getenv("OPENAI_API_KEY"):
    st.error(
        "❌ 请在 .env 文件中设置：\n"
        "DEESEEK_API_KEY=sk-你的DeepSeek_API_Key\n"
        "OPENAI_API_KEY=sk-你的OpenAI_API_Key"
    )
    st.stop()

# —— 初始化客户端 ——
ds_client = OpenAI(api_key=os.getenv("DEESEEK_API_KEY"),
                   base_url="https://api.deepseek.com")
whisper_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# —— 会话状态初始化 ——


def init_state():
    defaults = {
        'speech_counter': 0,
        'players': {str(i): {'texts': []} for i in range(1, 13)},
        'my_role': '村民',
        'my_number': '1',
        'wolf_allies': [],
        'analysis': {},
        'selected_day': 1,
        'selected_stage': '上警发言',
        'selected_pid': '1'
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# —— 标题与样式 ——
st.title('🎭 狼人杀AI分析助手')
st.markdown(
    """
    <style>
    div[data-baseweb=\"radio\"] > label > div[role=\"radio\"][aria-checked=\"true\"] {
      background-color: #ffdddd !important;
      border-radius: 4px;
      padding: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

# —— 侧边栏配置 ——
with st.sidebar:
    st.header('⚙️ 游戏配置')
    st.session_state.my_role = st.selectbox(
        '你的身份', ['村民', '狼人', '预言家', '女巫', '猎人'],
        index=['村民', '狼人', '预言家', '女巫', '猎人'].index(st.session_state.my_role)
    )
    st.session_state.my_number = st.selectbox(
        '我的玩家编号', [str(i) for i in range(1, 13)],
        index=int(st.session_state.my_number)-1
    )
    if st.session_state.my_role == '狼人':
        allies = st.text_input('狼人队友（逗号分隔）', value=','.join(
            st.session_state.wolf_allies))
        if st.button('保存队友'):
            st.session_state.wolf_allies = [
                p.strip() for p in allies.split(',') if p.strip()]
            st.success(f'✅ 已保存狼队友：{st.session_state.wolf_allies}')

# —— 发言记录 ——
st.header('📝 发言记录')
st.session_state.selected_day = st.number_input(
    '第几天', min_value=1, value=st.session_state.selected_day, step=1)
default_idx = 0 if st.session_state.selected_day == 1 else 1
st.session_state.selected_stage = st.radio(
    '选择阶段', ['上警发言', '讨论发言'], index=default_idx, horizontal=True)
st.session_state.selected_pid = st.select_slider('选择玩家编号', options=[str(
    i) for i in range(1, 13)], value=st.session_state.selected_pid)
st.write(f"已选：Day{st.session_state.selected_day} • {st.session_state.selected_stage} • 玩家{st.session_state.selected_pid}")
speech = st.text_input('输入发言内容')
if st.button('添加发言') and speech.strip():
    st.session_state.speech_counter += 1
    entry = {'day': st.session_state.selected_day, 'stage': st.session_state.selected_stage,
             'pid': st.session_state.selected_pid, 'text': speech.strip(), 'order': st.session_state.speech_counter}
    st.session_state.players[entry['pid']]['texts'].append(entry)
    st.success(f"✅ 记录第{entry['order']}条：{entry['text']}")

# —— 发言历史 ——
st.header('📖 发言历史')
for pid, info in st.session_state.players.items():
    with st.expander(f'玩家 {pid}'):
        for e in sorted(info['texts'], key=lambda x: x['order']):
            st.write(f"[{e['order']}] Day{e['day']} {e['stage']}：{e['text']}")

# —— 身份概率与一句话总结 ——
st.divider()
st.subheader('🔮 身份概率与总结')
if st.button('开始思考'):
    with st.spinner('分析中，请稍候...'):
        for pid, info in st.session_state.players.items():
            if not info['texts']:
                continue
            joined = '\n'.join([e['text'] for e in info['texts']])
            prompt = (
                f"你是{st.session_state.my_number}号玩家，你的身份是{st.session_state.my_role}\n"
                f"请基于玩家{pid}和其他之前玩家的发言，给出其身份概率和一句话总结，返回JSON：\n"
                f"{{\"role_probs\":{{\"狼人\":0-1,\"村民\":0-1,\"神职\":0-1}},\"summary\":\"一句话总结\"}}\n"
                f"发言：\n{joined}"
            )
            try:
                resp = ds_client.chat.completions.create(
                    model='deepseek-chat',
                    messages=[{'role': 'system', 'content': '你是狼人杀裁判，请返回指定JSON'},
                              {'role': 'user', 'content': prompt}],
                    temperature=0.3, max_tokens=300
                )
                raw = resp.choices[0].message.content.strip()
                start, end = raw.find('{'), raw.rfind('}')
                json_str = raw[start:end+1] if start > -1 and end > -1 else ''
                if not json_str:
                    st.error(f"玩家 {pid} 未返回JSON：{raw}")
                    continue
                try:
                    data = json.loads(json_str)
                except Exception:
                    st.error(f"玩家 {pid} JSON解析失败：{json_str}")
                    continue
                st.markdown(f"**玩家 {pid}**")
                st.markdown("- **身份概率:**")
                for role, prob in data['role_probs'].items():
                    st.markdown(f"  - {role}: {prob*100:.1f}%")
                st.markdown(f"- **一句话总结:** {data.get('summary', '')}")
            except Exception as e:
                st.error(f"玩家 {pid} 概率分析失败：{e}")
        # 自然语言分析
        st.subheader('🧠 思考细节（自然语言分析）')
        for pid, info in st.session_state.players.items():
            if not info['texts']:
                continue
            joined = '\n'.join([e['text'] for e in info['texts']])
            prompt = f"请用自然语言分析玩家{pid}可能身份及理由，发言：\n{joined}"
            try:
                resp = ds_client.chat.completions.create(
                    model='deepseek-chat',
                    messages=[{'role': 'system', 'content': '你是专业狼人杀玩家。'},
                              {'role': 'user', 'content': prompt}],
                    temperature=0.3, max_tokens=300
                )
                st.markdown(f"**玩家 {pid} 分析：**")
                st.write(resp.choices[0].message.content.strip())
            except Exception as e:
                st.error(f"玩家 {pid} 自然语言分析失败：{e}")

# —— 导出数据 ——
with st.sidebar:
    st.divider()
    st.download_button('💾 导出数据', data=json.dumps(st.session_state.players, ensure_ascii=False,
                       indent=2), file_name='session_data.json', mime='application/json')
