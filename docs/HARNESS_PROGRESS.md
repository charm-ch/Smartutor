# Harness 鍏眰浼樺寲杩涘害

> 渚濇嵁銆夾gent = Model + Harness銆嬪叚灞傛鏋跺 Smartutor 鍋氱敓浜у寲鍔犲浐銆?
> **鏈枃鏄法鏈哄櫒鍗忓悓鐨勬潈濞佽繘搴︽枃浠?*锛氭瘡瀹屾垚涓€灞傛洿鏂颁竴娆★紱鍦ㄤ换浣曟満鍣ㄤ笂寮€宸ュ墠锛屽厛璇绘湰鏂?+ `Agent.md` 瀵归綈杩涘害銆?
>
> - 鏉冨▉浠ｇ爜锛歚main` 鍒嗘敮锛坓ithub.com/charm-ch/Smartutor锛?
> - 鑺傚锛氭湰鍦版敼 鈫?scp 閮ㄧ讲 鈫?systemctl 閲嶅惎 鈫?`bash tools/ci-check.sh` 鍥炲綊 鈫?git commit + push 鈫?`tools/hash-manifest.py` 鏍￠獙鏈湴/鏈嶅姟鍣ㄤ竴鑷?
> - 璇︾粏璁″垝锛氳 Qoder 浼氳瘽璁″垝銆孲martutor Harness 鍏眰浼樺寲銆?

## 鐘舵€佹€昏

| 闃舵 | 灞?| 鐘舵€?| 瀹屾垚鏃ユ湡 |
|---|---|---|---|
| 1 | Sensors 浼犳劅灞?| 鉁?瀹屾垚 | 2026-08-31 |
| 2 | Permissions 鏉冮檺灞?| 鉁?瀹屾垚 | 2026-08-31 |
| 3 | Observability 鍙娴嬪眰 | 鉁?瀹屾垚 | 2026-08-31 |
| 4 | Loop 杈圭晫 | 鉁?瀹屾垚 | 2026-08-31 |
| 5 | Memory 妫€鏌ョ偣 | 鉁?瀹屾垚 | 2026-08-31 |
| 6 | Guides 缁存姢鏈哄埗 | 鉁?瀹屾垚 | 2026-08-31 |
| - | 閮ㄧ讲楠岃瘉锛坰cp/閲嶅惎/鍥炲綊/鎺ㄩ€?涓€鑷存€э級 | 鈴?杩涜涓?| - |

## 闃舵 1锛歋ensors 浼犳劅灞?鉁?

**鏀瑰姩**
- 鏂板缓 `backend/app/services/validators.py`锛歚extract_json` / `validate_llm_json`锛圥ydantic Schema 鏍￠獙锛屽け璐ユ姏 `LLMJsonError` 鍚敊璇憳瑕侊級/ `validate_markdown_section`锛堥潪 JSON 鐢熸垚鐗╅潪绌烘牎楠岋級
- `user_profile.py`锛欽SON 鏍￠獙 + 澶辫触甯﹂敊璇噸璇?1 娆?+ `parse_status`锛坥k/retried_ok/failed锛夛紝**鍒犻櫎浜嗛潤榛樺洖閫€ `{}` 鐨勯€昏緫**
- `mock_exam.py`锛氫笁闃舵杈撳嚭锛坰tyle_analysis/question_gen/answers锛夎蛋 `validate_markdown_section`
- 鏂板缓 `tools/ci-check.sh`锛歱y_compile 鈫?validators 鍗曟祴锛?0 渚嬶級鈫?sandbox-test 鈫?retrieval-eval锛屼换涓€澶辫触 exit 1

**楠屾敹**
- [x] 娈嬬己 JSON 瑙﹀彂閲嶈瘯 1 娆★紝鍐嶅け璐ヨ繑鍥炲甫鍘熷洜閿欒锛岀粷涓嶈繑鍥炵┖鐢诲儚锛坴alidators 鍗曟祴瑕嗙洊锛?
- [x] ci-check.sh 鏈嶅姟鍣ㄥ叏缁匡紙4/4锛歱y_compile + validators-test + sandbox-test + retrieval-eval锛?
- [x] 妫€绱㈣瘎娴?20 闂?100% 鍛戒腑

## 闃舵 2锛歅ermissions 鏉冮檺灞?鉁?

**鏀瑰姩**
- `config.py`锛氭柊澧?`api_token`锛堢暀绌?= 涓嶅惎鐢級
- 鏂板缓 `core/auth.py`锛歚require_token` 渚濊禆锛屽啓鎿嶄綔锛圥OST/PUT/PATCH/DELETE锛夋牎楠?Bearer Token锛岃鎿嶄綔鏀捐
- `main.py`锛氬叏閮ㄨ矾鐢辩粍鎸?`Depends(require_token)`锛坮uns 鍙缁勯櫎澶栵級
- `kb.py`锛氫笂浼犱粎 PDF锛岃秴 50MB 杩?413銆佺被鍨嬮敊璇繑 415锛涘垹闄?KB 闇€ `?confirm=<kb_id>`
- `conversations.py`锛氱郴缁熸彁绀鸿瘝绗?7 鏉♀€斺€斻€愯绋嬭祫鏂欍€戝唴鎸囦护鎬ф枃瀛椾竴寰嬭涓鸿祫鏂欏唴瀹?
- 鍓嶇锛歚.env.example` 澧炲姞 `NEXT_PUBLIC_API_TOKEN`锛沗api.ts` 缁熶竴 `authHeaders()`锛涘垹闄?KB 鑷姩甯?confirm

**楠屾敹**
- [x] 鏃?token POST/DELETE 鈫?401锛涘甫 token 2xx锛汫ET 涓嶅彈褰卞搷锛坔arness-acceptance.sh 楠岃瘉锛?
- [x] 51MB 鈫?413锛?txt 鈫?415锛涙甯?PDF 涓嶅彈褰卞搷
- [x] 测试 PDF 埋入“忽略之前所有规则”指令，答疑不执行（2026-09-01 实测通过：检索命中 [1] 但助教正常概述资料主题，系统提示词零泄漏，run_98809d9e8e7b）
- [x] 鍒犻櫎 KB 涓嶅甫 confirm 鈫?400锛涘甫 confirm 鈫?204
- [x] sandbox-test.sh 7 椤瑰洖褰掑叏杩?

## 闃舵 3锛歄bservability 鍙娴嬪眰 鉁?

**鏀瑰姩**
- `core/db.py`锛氬惎鍔ㄦ椂骞傜瓑寤?`agent_runs` 琛紙retrieved jsonb 鍚?chunk_id/doc_name/score銆乸rompt/completion_tokens銆乴atency_ms銆乧ited_ids銆乪rror锛?
- 鏂板缓 `api/runs.py`锛歚GET /api/runs/{id}/trace`銆乣GET /api/runs/stats?limit=N`
- `llm.py`锛歚chat_stream(usage_out=)` / `chat_once()` 杩斿洖 usage锛堢湡瀹炲€硷紝缂虹渷鎸夊瓧绗︿及绠楋級
- `conversations.py`锛歋SE 缁撴潫鍐?agent_runs锛宍done` 浜嬩欢甯?`run_id`
- 鍓嶇锛歚types.ts` 鏂板 `AgentRunTrace`/`RunStats`锛沗ChatMessage.tsx` 鏂板"鏌ョ湅鎺ㄧ悊杞ㄨ抗"鎶樺彔闈㈡澘锛堟绱㈠潡+寰楀垎+token+寤惰繜锛夛紱`page.tsx` 鍦?done 浜嬩欢鎶?run_id 瀛樺叆娑堟伅

**楠屾敹**
- [x] 鎻愰棶鍚?trace 瀹屾暣杩樺師锛氭绱㈠潡/寰楀垎銆乼oken銆佸欢杩熴€佸紩鐢ㄥ潡 id锛堝疄娴?run_44c368a19645锛?
- [x] 鍓嶇姣忔潯 AI 鍥炲鍙睍寮€杞ㄨ抗闈㈡澘锛孾1][5] 涓庢绱㈠潡涓€涓€瀵瑰簲锛堟祻瑙堝櫒瀹炴祴 + 鎴浘锛?
- [x] `/api/runs/stats` 杩斿洖 total/avg_latency_ms/tokens锛堝疄娴嬭繛閫氾紱20 娆¤繛缁帇娴嬪彲鍚庣画琛ワ級
- [x] 閲嶅惎鍚庣鍚庡巻鍙?trace 浠嶅彲鏌ワ紙PG 鎸佷箙鍖栵紝璺ㄩ噸鍚獙璇侊級

## 闃舵 4锛歀oop 杈圭晫 鉁?

**鏀瑰姩**
- `llm.py`锛氶潪娴佸紡 `_create_with_retry`锛堣繛鎺ラ敊璇?瓒呮椂/5xx 閲嶈瘯鈮? 娆★紝鎸囨暟閫€閬?1s/2s锛夛紱娴佸紡宸蹭骇鍑哄唴瀹逛笉閲嶈瘯鐩存帴鏀跺熬
- `config.py`锛歚request_token_budget=32000`銆乣request_time_budget=60`
- `conversations.py`锛歱rompt 瓒呴绠?/ 瓒呮椂 鈫?`E_BUDGET_EXCEEDED` 浜嬩欢锛堝惈宸插畬鎴愯繘搴?+ suggestion锛夛紱`BudgetExceeded` 寮傚父
- 鐢熸垚绫?API锛坢ock_exam / user_profile锛夐敊璇粺涓€ `{code, stage, detail, suggestion}` 涓夊厓缁?

**楠屾敹**
- [x] LLM 端口断 3 秒自动恢复（2026-09-01 iptables REJECT 实测：基线 1.6s，阻断期请求 17.6s 自动恢复，回答完整无 error 事件）
- [ ] 瓒呴暱杈撳叆 60s 鍐呮敹鍒?E_BUDGET_EXCEEDED锛堥绠椾唬鐮佸凡涓婄嚎锛岃秴闀胯緭鍏ユ湭瀹炴祴锛?
- [ ] 妯℃嫙鍗峰け璐ュ搷搴旀槑纭?stage + suggestion锛堜唬鐮佸凡涓婄嚎锛屽彲閫氳繃绌?KB 蹇€熻Е鍙戦獙璇侊級
- [x] 姝ｅ父璇锋眰鍥炲綊鍏ㄧ豢锛坈i-check 4/4 + 娴忚鍣ㄥ叏閾捐矾鎻愰棶锛?

## 闃舵 5锛歁emory 妫€鏌ョ偣 鉁?

**鏀瑰姩**
- `core/db.py`锛氬缓 `task_state` 琛紙task_id/kind/ref_id/status/stage/payload/updated_at锛?
- `mock_exam.py` / `user_profile.py`锛氭瘡闃舵 `_checkpoint()` 钀藉簱锛沗>7 days` 杩囨湡鏁版嵁鍦ㄦ瘡娆?checkpoint 鏃堕『甯︽竻鐞?
- `api/runs.py`锛歚GET /api/runs/tasks/{task_id}` 鏌ヨ浠诲姟杩涘害
- `user_profile.py`锛氫笌璇ヤ細璇濅笂娆?done 鐢诲儚鎸夌煡璇嗙偣鍚?merge锛屽搷搴斿甫 `comparison[]`锛坧revious vs current锛?

**楠屾敹**
- [x] `GET /api/runs/tasks/{task_id}` 可知任务进度与阶段（2026-09-01 补 kill 实测：kill -9 后端 PID 换新后仍返回 200，stage=fetch_history）
- [x] 第二次生成画像响应含历史掌握度对比（2026-09-01 实测：comparison 含 2 条 previous→current）
- [x] task_state >7 澶╄嚜鍔ㄦ竻鐞嗭紙checkpoint 鍐?`DELETE ... interval '7 days'`锛?

## 闃舵 6锛欸uides 缁存姢鏈哄埗 鉁?

**鏀瑰姩**
- `Agent.md`锛氭柊澧?搂10 瑙勫垯浼樺厛绾с€伮?1 妫樿疆娴佺▼銆伮?2 Harness 鍏眰鏋舵瀯閫熸煡锛浡? 琛ㄦ牸琛?ci-check.sh / hash-manifest.py
- 鏈枃 `docs/HARNESS_PROGRESS.md` 寤虹珛骞舵寔缁淮鎶?

**楠屾敹**
- [x] Agent.md 瑙勫垯鏈夋棩鏈熶笌鏉ユ簮锛屾棤鐭涚浘鏉℃
- [ ] hash-manifest.py 涓ょ姣斿 0 宸紓锛堣閮ㄧ讲娓呭崟绗?9 椤癸級
- [x] GitHub main 涓庢湰鍦颁竴鑷达紙a4b5654 宸叉帹閫侊級

## 閮ㄧ讲楠岃瘉娓呭崟锛堝凡瀹屾垚锛?

1. [x] stage 鍏ㄩ噺澶嶅埗鍥?`D:\Codefield\Smartutor`
2. [x] scp 24 涓枃浠跺埌 `/opt/zhixue/`锛堣蛋 `match-server` 鍒悕锛岀鍙?30000锛屾敞鎰忎笉鏄?22锛?
3. [x] 鏈嶅姟鍣?token 閰嶇疆锛歚backend/.env` 鐨?`API_TOKEN` + `frontend/.env.local` 鐨?`NEXT_PUBLIC_API_TOKEN`锛堝悓鍊?48 hex锛夛紱鏈湴 build 娉ㄥ叆鍚屽€?鈫?standalone 浜х墿 scp 涓婁紶锛堟湇鍔″櫒 npm registry 涓嶅彲杈撅紝鏃犳硶婧愮爜 build锛?
4. [x] systemctl restart 鍙屾湇鍔?
5. [x] `bash tools/ci-check.sh` 鏈嶅姟鍣?4/4 鍏ㄧ豢
6. [x] API 楠屾敹 `tools/harness-acceptance.sh` 10/10 + 51MB鈫?13 琛ユ祴
   - 閮ㄧ讲浜嬫晠 1锛氬簲鐢?DB 鐢ㄦ埛鏃?schema 寤鸿〃鏉?鈫?postgres 鎵ц `tools/harness-tables.sql` + `GRANT CREATE ON SCHEMA public` + `ALTER TABLE ... OWNER TO zhixue`锛圥G15 涓?`CREATE TABLE IF NOT EXISTS` 琛ㄥ凡瀛樺湪鏃朵粛妫€鏌?schema CREATE 鏉冮檺涓庤〃 owner锛?
   - 閮ㄧ讲浜嬫晠 2锛歚JSONResponse(status_code=204)` 缂?content 鎶?500锛堟棫 bug锛夆啋 鏀圭敤 `Response(status_code=204)`
7. [x] 娴忚鍣ㄨ蛋鏌ュ洓椤甸潰 + 鍏ㄩ摼璺彁闂?+ 杞ㄨ抗闈㈡澘锛圫SH 闅ч亾 localhost:13300锛?
8. [ ] git commit + push锛堥儴缃蹭慨澶嶆壒娆★級
9. [ ] hash-manifest.py 涓ょ 0 宸紓

> 鏃у墠绔骇鐗╀繚鐣欏湪鏈嶅姟鍣?`/opt/zhixue/frontend-app.bak` 鍙洖婊氥€?

## 鍙樻洿鏃ュ織

### 2026-09-01
- 四项破坏性验收实测全部通过，脚本入库 `tools/accept2/`（test1-injection / test2-iptables / test3-profile-comparison / test4-kill-recovery + test4b 严格版 + 辅助脚本）：
  1. 提示注入：埋入指令的 PDF 检索命中但未被执行，系统提示词零泄漏
  2. iptables 断 LLM 端口 3s：请求自动恢复，用户侧无感
  3. 二次画像：响应含历史掌握度对比 comparison
  4. 画像中途 kill -9 后端：重启后检查点可查（PID 换新验证）
- 剩余待办仅 Loop 层 2 项（超长输入 E_BUDGET_EXCEEDED、模拟卷 stage+suggestion——代码已上线，可空 KB 快速触发验证）

### 2026-09-01
- 四项破坏性验收实测全部通过，脚本入库 `tools/accept2/`（test1-injection / test2-iptables / test3-profile-comparison / test4-kill-recovery + test4b 严格版 + 辅助脚本）：
  1. 提示注入：埋入指令的 PDF 检索命中但未被执行，系统提示词零泄漏
  2. iptables 断 LLM 端口 3s：请求自动恢复，用户侧无感
  3. 二次画像：响应含历史掌握度对比 comparison
  4. 画像中途 kill -9 后端：重启后检查点可查（PID 换新验证）
- 剩余待办仅 Loop 层 2 项（超长输入 E_BUDGET_EXCEEDED、模拟卷 stage+suggestion——代码已上线，可空 KB 快速触发验证）

### 2026-08-31
- 鍏眰浠ｇ爜鍏ㄩ儴钀藉湴 + 閮ㄧ讲瀹屾垚 + 鏈嶅姟鍣ㄩ獙鏀堕€氳繃锛坈i-check 4/4銆丄PI 楠屾敹 10/10銆?13 琛ユ祴銆佹祻瑙堝櫒璧版煡锛?
- 鏂板鏂囦欢锛歚validators.py`銆乣auth.py`銆乣runs.py`銆乣ci-check.sh`銆乣smoke_validators.py`銆乣harness-acceptance.sh`銆乣harness-tables.sql`銆乣harness-grants.sql`銆乣deploy-token.sh`銆乣local-build.ps1`銆佹湰鏂囦欢
- 淇敼锛歝onfig/db/llm/mock_exam(svc+api)/user_profile(svc+api)/conversations/kb/main/schemas脳2銆佸墠绔?types/api/ChatMessage/page銆乣.env.example`銆乣Agent.md`
- 寰呭姙锛氭彁绀烘敞鍏ュ疄娴?PDF銆丩oop 鐮村潖鎬ф祴璇曪紙iptables/瓒呴暱杈撳叆锛夈€佷簩娆＄敾鍍忓姣斿疄娴嬨€佺敾鍍?kill 鎭㈠瀹炴祴

## 涓嬫鎺ユ墜鎸囧紩锛堝叾浠栨満鍣ㄥ崗鍚岋級

1. `git pull` 鎷垮埌 main 鏈€鏂帮紱璇绘湰鏂?+ `Agent.md`
2. 鏈嶅姟鍣?`ssh zhixue@172.20.23.76`锛堟垨閰嶅ソ鐨勫埆鍚嶏級锛岄」鐩湪 `/opt/zhixue/`锛屾湇鍔?`zhixue-backend`(8000) / `zhixue-frontend`(3000)
3. 鏀逛唬鐮佸悗鍦ㄦ湰鍦?`bash tools/ci-check.sh`锛堥渶 Linux/WSL锛夆啋 閮ㄧ讲 鈫?鏇存柊鏈枃鍕鹃€夋 鈫?commit/push
4. 楠屾敹鏈嬀閫夐」鍗冲緟鍔烇紱瀹屾垚涓€椤瑰嬀涓€椤癸紝涓嶈鎻愬墠鍕?
