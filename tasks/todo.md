# TODO

- [x] 버전/업데이트 메타데이터 구조 확인 (`config.py`, `version.json`, `build.py`)
- [x] `config.py` 버전을 `2.1.1`로 상향
- [x] `./.venv/Scripts/python.exe build.py --target all`로 런처/업데이터 재빌드
- [x] 생성 EXE SHA256 계산
- [x] `version.json`의 `min_version`, `app_url`, `app_sha256`, `updater_sha256` 동기화
- [x] SHA 재검증으로 자동업데이트 메타데이터 일치 확인

# Review (to fill after implementation)

- 구현 요약: `config.py`를 `2.1.1`로 상향하고, `./.venv/Scripts/python.exe build.py --target all`로 `LTS V2.1.1.exe`, `LTS-Updater.exe`를 재빌드한 뒤 루트 산출물 SHA256으로 `version.json`을 동기화했다.
- 검증 결과:
  - app sha256: `ff90cdcc5669a39940f801e592d1bdb9b740c7504fa20509340e545e53833fbd`
  - updater sha256: `548b69fff36dd705affc629aaae8e45f3e616500480b82639373f887b61ac26a`
  - `version.json` 메타 SHA와 파일 실제 SHA 일치 확인 완료(`app_sha_match=True`, `updater_sha_match=True`).
- 잔여 리스크: GitHub 배포 시 `LTS V2.1.1.exe`, `LTS-Updater.exe`, `version.json`이 같은 커밋/배포 단위로 올라가지 않으면 일시적으로 업데이트 검증 실패가 발생할 수 있다.
