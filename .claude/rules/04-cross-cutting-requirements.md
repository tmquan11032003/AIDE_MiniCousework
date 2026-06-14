# Rule: Yêu cầu xuyên suốt mọi section

Mỗi section phải **hướng triển khai**, không chỉ khái niệm. Bao phủ:
- Assumptions + ranh giới scope.
- Inputs/outputs rõ ràng + data contract.
- Xử lý lỗi + cách phục hồi (retry, dead-letter/quarantine, rerun idempotent).
- Observability: logs, metrics, traces.
- Security cơ bản: auth, RBAC, secrets, xử lý dữ liệu nhạy cảm (PII).
- Ý định CI/CD cho service/pipeline trong scope.
