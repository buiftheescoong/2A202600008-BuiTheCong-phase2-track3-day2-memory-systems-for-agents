"""10 multi-turn benchmark conversation scenarios.

Covers all 5 required test groups:
- Profile recall (2)
- Conflict update (2)
- Episodic recall (2)
- Semantic retrieval (2)
- Trim/token budget (1)
- Mixed recall (1)
"""

# Each scenario: list of (user_message, expected_key_in_response) tuples
# expected_key_in_response: keyword(s) the with-memory agent SHOULD mention

SCENARIOS: list[dict] = [
    # === 1. Profile recall: remember user name ===
    {
        "id": 1,
        "name": "Recall user name after multiple turns",
        "group": "profile_recall",
        "turns": [
            ("Xin chào, tôi là Linh.", None),
            ("Hôm nay trời đẹp quá nhỉ?", None),
            ("Tôi đang học Python.", None),
            ("Bạn có biết framework nào hay không?", None),
            ("Cảm ơn bạn nhiều!", None),
            ("Bạn còn nhớ tên tôi không?", "Linh"),
        ],
    },
    # === 2. Conflict update: allergy correction ===
    {
        "id": 2,
        "name": "Allergy conflict update",
        "group": "conflict_update",
        "turns": [
            ("Tôi bị dị ứng sữa bò.", None),
            ("Gợi ý cho tôi một món ăn sáng nhé.", None),
            ("À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.", None),
            ("Vậy tôi bị dị ứng gì nhỉ?", "đậu nành"),
        ],
    },
    # === 3. Profile recall: favorite programming language ===
    {
        "id": 3,
        "name": "Recall favorite programming language",
        "group": "profile_recall",
        "turns": [
            ("Ngôn ngữ lập trình yêu thích của tôi là Rust.", None),
            ("Tôi cũng thích viết Go nữa.", None),
            ("Hôm nay tôi đang làm project mới.", None),
            ("Bạn có gợi ý gì cho project không?", None),
            ("Ngôn ngữ yêu thích của tôi là gì?", "Rust"),
        ],
    },
    # === 4. Episodic recall: remember debug lesson ===
    {
        "id": 4,
        "name": "Recall debug lesson from previous session",
        "group": "episodic_recall",
        "setup_episodes": [
            {
                "summary": "Học được cách debug Docker: dùng docker service name thay vì localhost",
                "context": "User gặp lỗi connection refused khi container gọi localhost",
                "outcome": "Dùng tên service trong docker-compose thay vì localhost",
                "tags": ["docker", "debug", "networking"],
            }
        ],
        "turns": [
            ("Tôi đang gặp vấn đề với Docker networking.", None),
            ("Container không kết nối được với database.", None),
            ("Lần trước tôi đã học được bài học gì về Docker nhỉ?", "service"),
            ("Cảm ơn, tôi nhớ rồi!", None),
        ],
    },
    # === 5. Semantic retrieval: FAQ about Docker ===
    {
        "id": 5,
        "name": "Retrieve Docker networking FAQ",
        "group": "semantic_retrieval",
        "turns": [
            ("Làm sao để container A gọi container B trong docker-compose?", "service"),
            ("Có cách nào khác không?", None),
            ("Cảm ơn bạn!", None),
        ],
    },
    # === 6. Episodic recall: previous conversation topic ===
    {
        "id": 6,
        "name": "Recall previous conversation topic",
        "group": "episodic_recall",
        "setup_episodes": [
            {
                "summary": "Thảo luận về cách tối ưu database query bằng indexing",
                "context": "User hỏi về performance issue với PostgreSQL query chậm",
                "outcome": "Thêm composite index cho các cột thường query cùng nhau",
                "tags": ["database", "postgresql", "indexing", "performance"],
            }
        ],
        "turns": [
            ("Hôm nay tôi lại gặp vấn đề performance database.", None),
            ("Lần trước chúng ta đã nói về gì liên quan database nhỉ?", "index"),
            ("Đúng rồi, cảm ơn bạn!", None),
            ("Tôi sẽ thử áp dụng indexing cho project mới.", None),
            ("Bạn có gợi ý thêm gì không?", None),
        ],
    },
    # === 7. Conflict update: food preference ===
    {
        "id": 7,
        "name": "Food preference conflict update",
        "group": "conflict_update",
        "turns": [
            ("Món ăn yêu thích của tôi là phở.", None),
            ("Tôi hay ăn sáng bằng phở.", None),
            ("Thực ra tôi thích bún bò hơn phở, tôi đổi ý rồi.", None),
            ("Món ăn yêu thích của tôi là gì?", "bún bò"),
        ],
    },
    # === 8. Semantic retrieval: Python best practices ===
    {
        "id": 8,
        "name": "Retrieve Python best practices from knowledge base",
        "group": "semantic_retrieval",
        "turns": [
            ("Khi nào nên dùng dataclass thay vì Pydantic?", "validation"),
            ("Còn environment variables thì sao?", "dotenv"),
            ("Cảm ơn, rất hữu ích!", None),
        ],
    },
    # === 9. Token budget trim: long conversation ===
    {
        "id": 9,
        "name": "Long conversation - trim/token budget test",
        "group": "trim_token_budget",
        "turns": [
            ("Tôi tên là Nam, là software engineer.", None),
            ("Tôi đang làm việc ở công ty ABC, chuyên về backend development.", None),
            ("Tech stack của tôi gồm Python, FastAPI, PostgreSQL, Redis, Docker.", None),
            ("Hôm nay tôi đang refactor một microservice lớn.", None),
            ("Service này xử lý payment processing cho e-commerce platform.", None),
            ("Tôi cần tối ưu latency từ 500ms xuống 200ms.", None),
            ("Đã thử cache layer nhưng chưa đủ.", None),
            ("Bạn có nhớ tên tôi và tech stack tôi dùng không?", "Nam"),
        ],
    },
    # === 10. Mixed: profile + episodic + semantic ===
    {
        "id": 10,
        "name": "Mixed recall: profile + episodic + semantic",
        "group": "mixed_recall",
        "setup_episodes": [
            {
                "summary": "Hoàn thành project API gateway bằng FastAPI",
                "context": "User build API gateway cho microservices architecture",
                "outcome": "Deploy thành công, latency giảm 40%",
                "tags": ["fastapi", "api-gateway", "microservices"],
            }
        ],
        "turns": [
            ("Tôi là Minh, senior developer.", None),
            ("Tôi thích dùng FastAPI cho backend.", None),
            ("Cách xử lý environment variables an toàn như thế nào?", "dotenv"),
            ("Lần trước tôi đã làm project gì với FastAPI nhỉ?", "API gateway"),
            ("Bạn có nhớ tên tôi không?", "Minh"),
            ("Tổng hợp lại những gì bạn biết về tôi.", None),
        ],
    },
]
