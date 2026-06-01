---
name: IP 대신 toby.local 사용
description: 네트워크 연결 시 하드코딩 IP 대신 mDNS(toby.local) 사용 필수
type: feedback
originSessionId: c9c717fe-e0f9-434c-98a0-66869ce3d6e6
---
PC ↔ RPi5 통신에서 IP 주소를 하드코딩하지 말고 반드시 `toby.local` (mDNS)을 사용할 것.

**Why:** WiFi를 바꿀 때마다 IP가 달라져서 매번 코드를 수정해야 했음. 2026-05-27 세션에서 5개 파일의 DEFAULT_HOST를 전부 `toby.local`로 변경함.

**How to apply:** 새로운 네트워크 관련 코드를 작성할 때 RPi5 주소는 항상 `toby.local`로 지정. IP 직접 입력(172.17.18.46 등)은 피할 것.
