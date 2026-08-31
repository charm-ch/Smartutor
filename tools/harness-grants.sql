-- 检查与授权：agent_runs/task_state 给应用用户 zhixue 完全权限
\echo === owners ===
SELECT tablename, tableowner FROM pg_tables WHERE tablename IN ('agent_runs','task_state','messages');
GRANT ALL ON agent_runs TO zhixue;
GRANT ALL ON task_state TO zhixue;
\echo === done ===
