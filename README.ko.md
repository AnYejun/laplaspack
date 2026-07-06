# laplaspack 만들기 — 한국어 안내

> **당신의 기억을 파일 하나로.**
> `.laplaspack`은 노트·회사 스토리·연구 기록을 **AI가 근거를 대며 답하고, 당신이 직접 고칠 수 있는
> 이식 가능한 기억 파일**로 만든 것입니다. SQLite 파일 하나라서 이메일로 보내고,
> 깃에 넣고, 어떤 AI에든 꽂을 수 있습니다 — 서버 없이, 계정 없이.

이 문서는 **팩을 만들러 온 분들을 위한 한국어 가이드**입니다.
포맷의 정식 명세(영문)는 [`SPEC.md`](./SPEC.md), 전체 개요는 [`README.md`](./README.md)를 보세요.
우리가 왜 이 포맷을 만들었는지는 [선언(MANIFESTO.ko.md)](./MANIFESTO.ko.md)에 있습니다 — **기억은 결과가 아니라 맥락이다.**

---

## 30초 개념

일반 메모는 "글자 덩어리"라서 AI가 **왜**를 답하지 못합니다.
laplaspack은 쓰는 순간에 구조를 잡습니다:

```
일반 텍스트:  "Neo4j SSL 에러 때문에 Supabase로 전환했다"
              → AI는 이 문장을 통째로 외울 뿐, '왜'를 걸어가지 못함

LMD:          [[Supabase 전환]] →(derived-from) [[Neo4j SSL 에러]]
              → "왜 전환했어?" 라고 물으면 이 화살표를 따라 근거를 인용함
```

- **LMD** (LAPLAS Markdown) = 사람이 읽고 쓰는 원본 텍스트. 마크다운에 세 가지 문법만 추가.
- **laplaspack** = LMD를 컴파일한 결과물. 파일 하나 = 기억 하나.
- 만든 팩은 [Manifesto](https://laplas-manifesto.vercel.app)에 올리면 **출처를 인용하며
  답하는 웹 Q&A 페이지**가 되고, LAPLAS AX 콘솔에 마운트하면 에이전트의 기억이 됩니다.

---

## 만드는 법 세 가지 (쉬운 순서)

### ① 인터뷰로 만들기 — 자료가 아직 머릿속에만 있을 때 ★추천

[`prompts/manifesto-interview.md`](./prompts/manifesto-interview.md)의 프롬프트 블록을
Claude / ChatGPT / Gemini에 붙여넣으세요. **AI가 면접관이 되어 한 번에 하나씩 질문합니다** —
한국어로 답하면 됩니다. "빠르다"라고 하면 "얼마나요? 언제부터요? 누가 그래요?"라고
되묻는데, 그 추궁이 그대로 근거 링크가 됩니다. 끝나면 AI가 LMD를 만들고
빌드 명령까지 알려줍니다. 회사 소개(Manifesto)용으로 설계됐지만 개인 포트폴리오에도 좋습니다.

### ② 프롬프트로 컴파일하기 — 이미 써둔 자료가 있을 때

[`prompts/lmd-compiler.md`](./prompts/lmd-compiler.md)를 붙여넣고, 다음 메시지에
원자료(회사 소개서, 이력서, 프로젝트 노트, 회의록)를 붙여넣으세요. LMD가 나옵니다.
`story.lmd`로 저장한 뒤:

```bash
git clone https://github.com/AnYejun/laplaspack
cd laplaspack
python3 laplaspack_writer.py story.lmd --owner 이름 --name "내 팩"
python3 laplaspack_reader.py story.laplaspack --why "<결정 노드 라벨>"
```

파이썬 표준 라이브러리만 씁니다 — pip 설치가 필요 없습니다.

### ③ Claude Code로 만들기 — 한 마디로 끝내기

```bash
mkdir -p .claude/skills && cp -r skills/laplaspack .claude/skills/
```

그 다음 Claude Code에서: *"./docs 내용으로 laplaspack 만들어줘"*.
읽고, 컴파일하고, 빌드하고, `--why` 검증까지 알아서 합니다.

---

## LMD 미니 강좌 — 문법은 세 가지뿐

LMD는 마크다운에 **세 가지 모양**을 더한 것입니다.
**모든 사실은 셋 중 정확히 한 층위에 놓입니다** — 이게 전부입니다.

### 1. 노드 — 가리킬 수 있는 "것"

사람, 팀, 프로젝트, 개념, 목표, 결정. 라벨은 **명사구**입니다.

```lmd
## 김하나 (Hana Kim)
[[김하나 (Hana Kim)]]
>>type: person
>>what: 프로를 꿈꾸는 동산중 축구부 미드필더.
```

### 2. 속성 — 한 노드에 대한 스칼라 사실

키, 생일, 가격, 날짜 같은 값은 **노드 위에 `>>키: 값`으로** 적습니다.

```lmd
>>born: 2011-03-02
>>height: 166cm
>>position: 미드필더
```

### 3. 링크 — 두 노드 사이의 관계

```lmd
[[김하나 (Hana Kim)]] →(plays-for) [[동산중 축구부 (Dongsan FC)]]
[[김하나 (Hana Kim)]] →(child-of) [[김민호 (Minho Kim)]]
[[전술 변경]] →(derived-from) [[3연패 분석]]
```

- **인과 6종** — `derived-from` `supports` `raises` `closes` `supersedes`
  `contradicts` — 이 여섯이 `--why`(왜?) 체인을 움직입니다. 결정에는 반드시 근거를 이 화살표로.
- **도메인 관계** — `child-of`, `plays-for`, `uses`처럼 **아무 kebab-case 단어**나 됩니다.

### 판별법 한 줄

> 라벨이 **다른 노드에 대한 문장**으로 읽히면 그건 노드가 아닙니다.

```
❌ 이렇게 만들면 그래프가 아니라 낱장 목록이 됩니다:
   [[키 166cm]]  [[여자친구 있음]]  [[가장 좋아하는 팀 레알마드리드]]

✅ 사실을 제 층위에 놓으면:
   [[김하나]] >>height: 166cm            ← 속성
   [[김하나]] →(fan-of) [[레알 마드리드]]  ← 링크
```

### 생각도 기록할 수 있습니다 — `@@think@@`

날짜와 작성자가 붙는 "생각 문서"입니다. 할 일, 결정, 열린 질문에 쓰세요.

```lmd
@@todo on="전술 변경" by=hana at=2026-07-06 status=open id=t1
주말까지 4-3-3 전환 연습 — 코치 확인 필요
@@
```

---

## 자주 하는 실수 다섯 가지

| 실수 | 왜 문제인가 | 고치는 법 |
|---|---|---|
| 문장을 노드로 만듦 (`[[키 166cm]]`) | 그래프가 아니라 목록이 됨 | 속성(`>>height:`)이나 링크로 |
| **고아 노드** (링크 0개) | 검색·왜-체인에서 섬이 됨 — writer가 경고함 | 모든 노드를 허브(주인공)에 연결 |
| `>>아버지: [[홍길동]]` 으로 관계 표현 | **엣지가 되지 않고** 그냥 글자로 남음 | 관계는 화살표로: `[[A]] →(father) [[B]]` (예외: `part_of`·인과 6종 키는 필드로도 엣지가 됨) |
| `>>what:`에 모든 사실을 다 씀 | 속성과 중복, 검색 기판 낭비 | what은 한 줄 본질만, 사실은 속성으로 |
| 인과 role 오타 (`suports`) | `--why`가 못 걸어감 | writer가 근접 경고를 띄워줌 — 경고 0이 합격선 |

**writer의 경고는 장식이 아니라 계약입니다.** 경고가 하나라도 나오면 소스로 돌아가세요.

---

## 만들고 나서 — 팩의 세 가지 쓸모

1. **Manifesto** — [laplas-manifesto.vercel.app](https://laplas-manifesto.vercel.app)에
   업로드하면 방문자 질문에 **인용과 함께** 답하는 페이지가 됩니다. (무료 티어 월 100답변)
2. **MCP로 어디서나** — 계정 없이 로컬에서:
   ```json
   { "mcpServers": { "mypack": { "command": "python3",
     "args": ["laplaspack_mcp.py", "story.laplaspack"] } } }
   ```
   Claude Desktop 등 아무 MCP 클라이언트에서 `find / open / why / blind_spots` 사용 가능.
3. **LAPLAS AX** — [콘솔](https://laplas-ax.vercel.app)에 마운트하면 팀 에이전트의
   기억이 됩니다. 에이전트의 답에는 영수증이 남고, 기억 쓰기는 사람 승인을 거칩니다.

`.lmd` 원본이 **수정 가능한 진실의 원천**입니다 — 팩은 언제든 다시 빌드하면 됩니다.

---

## 파일 안내 (만들기에 필요한 것만)

| 파일 | 역할 |
|---|---|
| [`prompts/manifesto-interview.md`](./prompts/manifesto-interview.md) | 인터뷰로 만들기 (자료가 없을 때) |
| [`prompts/lmd-compiler.md`](./prompts/lmd-compiler.md) | 원자료 → LMD 컴파일 프롬프트 |
| [`skills/laplaspack/`](./skills/laplaspack/) | Claude Code 스킬 (한 마디로 제작) |
| [`laplaspack_writer.py`](./laplaspack_writer.py) | LMD → 팩 빌드 (+ 고아/오타/죽은링크 경고) |
| [`laplaspack_reader.py`](./laplaspack_reader.py) | 열기 · `--why` 체인 · `--todos` |
| [`laplaspack_mcp.py`](./laplaspack_mcp.py) | 아무 MCP 클라이언트에 팩 마운트 |
| [`kits/lab/`](./kits/lab/) | 살아있는 예시: 연구실 킷 (베끼기 좋은 출발점) |
| [`AUTHORING.md`](./AUTHORING.md) | 손으로 쓰는 법 상세 (영문) |

궁금한 점은 [Issues](https://github.com/AnYejun/laplaspack/issues)에 한국어로 남겨주세요.
