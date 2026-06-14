# Rule: Yêu cầu Data Engineering (bắt buộc)

- Phải có **cả** đường offline (batch) **và** streaming.
- Timestamp định nghĩa rõ và dùng nhất quán: `event_timestamp` (event time) vs `created_ts` (row creation/ingest time).
- Xét **point-in-time correctness** ở nơi liên quan (đặc biệt feature ↔ label join).
- Định nghĩa hành vi schema evolution / update.
- Thiết kế + demo **ít nhất một** kịch bản drift/change.

Thách thức nên chèn (chọn ít nhất một nhóm): skew/high-cardinality joins; bursty/late arrival/out-of-order; duplicates/missing/inconsistent format.
