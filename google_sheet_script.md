// ==========================================================
// [Part 1] 관리자가 시트를 수정할 때 실행되는 함수 (자동 날짜 갱신)
// ==========================================================
function onEdit(e) {
  var sheet = e.source.getActiveSheet();
  var range = e.range;
  var row = range.getRow();
  var col = range.getColumn();
  var val = range.getValue();

  // 조건 1: 제목줄(1~5행)이 아니고,
  // 조건 2: 수정된 곳이 E열(5번째 열, 상태창)이며,
  // 조건 3: 변경된 값이 "허가됨" 일 경우
  if (row > 5 && col == 5 && val == "허가됨") {
    
    // H열(8번째 열)에 오늘 날짜를 입력 (승인일/갱신일)
    // 날짜 포맷은 보기 좋게 설정
    var dateCell = sheet.getRange(row, 8);
    dateCell.setValue(new Date()); 
    dateCell.setNumberFormat("yy년 MM월 dd일");
  }
}

// ==========================================================
// [Part 2] 파이썬과 통신하는 함수 (로그인 검증 & 등록)
// ==========================================================
function doPost(e) {
  var lock = LockService.getScriptLock();
  try { lock.waitLock(10000); } catch (e) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "message": "Busy"}));
  }

  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // --------------------------------------------------
    // [LOGIC A] 로그인 권한 확인 (만료일 체크 포함)
    // --------------------------------------------------
    if (data.action == "check_login") {
      
      var startRow = 6;
      var lastRow = sheet.getLastRow();
      
      if (lastRow < startRow) {
        return ContentService.createTextOutput(JSON.stringify({"result": "fail"}));
      }

      // A열~H열까지 데이터 가져오기 (H열: 승인일)
      // 인덱스: A=0, B=1, ..., E=4(상태), ..., G=6(키), H=7(승인일)
      var range = sheet.getRange(startRow, 1, lastRow - startRow + 1, 8);
      var values = range.getValues();

      var loginResult = "fail";
      var targetRowIndex = -1;

      // 1. API Key 매칭 (G열 확인)
      for (var i = 0; i < values.length; i++) {
        if (values[i][6] == data.api_key) {
          targetRowIndex = i;
          break;
        }
      }

      // 2. 상태 판단 로직
      if (targetRowIndex != -1) {
        var status = values[targetRowIndex][4]; // E열: 상태
        var approvedDateStr = values[targetRowIndex][7]; // H열: 승인일 (New!)
        var today = new Date();

        // (1) 관리자: 날짜 상관없이 무조건 프리패스
        if (status == "관리자") {
          loginResult = "success";

        // (2) 허가됨: 30일 타이머 체크
        } else if (status == "허가됨") {
          
          // 만약 H열(승인일)이 비어있다면? -> 오늘로 넣어주고 통과시킬지, 막을지 결정.
          // 안전하게: 날짜가 없으면 막고 관리자 확인 요청.
          if (approvedDateStr == "" || approvedDateStr == null) {
            loginResult = "pending"; // 날짜 오류로 대기 처리
          } else {
            var approvedDate = new Date(approvedDateStr);
            var timeDiff = today.getTime() - approvedDate.getTime();
            var dayDiff = Math.ceil(timeDiff / (1000 * 3600 * 24));

            // 30일 초과 시 차단 및 상태 변경
            if (dayDiff > 30) {
              // 시트의 상태를 "허가되지 않음"으로 변경
              // (startRow + targetRowIndex) = 실제 엑셀 행 번호
              sheet.getRange(startRow + targetRowIndex, 5).setValue("허가되지 않음");
              loginResult = "banned";
            } else {
              loginResult = "success";
            }
          }

        // (3) 허가되지 않음
        } else if (status == "허가되지 않음") {
          loginResult = "banned";

        // (4) 등록요청
        } else {
          loginResult = "pending";
        }
      }

      return ContentService.createTextOutput(JSON.stringify({"result": loginResult})).setMimeType(ContentService.MimeType.JSON);
    }

    // --------------------------------------------------
    // [LOGIC B] 지갑 잔고 갱신 (I열)
    // --------------------------------------------------
    if (data.action == "update_balance") {
      var startRow = 6;
      var apiKey = data.api_key;
      var balanceValue = Number(data.balance);

      if (!apiKey || !isFinite(balanceValue)) {
        return ContentService.createTextOutput(
          JSON.stringify({"result": "fail", "message": "Invalid payload"})
        ).setMimeType(ContentService.MimeType.JSON);
      }

      var lastRow = sheet.getLastRow();
      if (lastRow < startRow) {
        return ContentService.createTextOutput(JSON.stringify({"result": "fail"})).setMimeType(ContentService.MimeType.JSON);
      }

      // G열(API Key)에서 사용자 찾기
      var keyValues = sheet.getRange(startRow, 7, lastRow - startRow + 1, 1).getValues();
      var targetRow = -1;
      for (var i = 0; i < keyValues.length; i++) {
        if (keyValues[i][0] == apiKey) {
          targetRow = startRow + i;
          break;
        }
      }

      if (targetRow == -1) {
        return ContentService.createTextOutput(JSON.stringify({"result": "fail"})).setMimeType(ContentService.MimeType.JSON);
      }

      // I열(9번째 열)에 "N USDT / NN년MM월DD일" 형식으로 저장
      var now = new Date();
      var dateText = Utilities.formatDate(now, Session.getScriptTimeZone(), "yy년MM월dd일");
      var balanceText = balanceValue.toFixed(2) + " USDT / " + dateText;
      var walletCell = sheet.getRange(targetRow, 9);
      walletCell.setValue(balanceText);
      walletCell.setHorizontalAlignment("center");

      return ContentService.createTextOutput(JSON.stringify({"result": "updated"})).setMimeType(ContentService.MimeType.JSON);
    }

    // --------------------------------------------------
    // [LOGIC C] 신규 등록 (기존 유지)
    // --------------------------------------------------
    var startRow = 6;
    var maxSearch = 6000;
    var targetRow = -1;
    var values = sheet.getRange(startRow, 2, maxSearch).getValues();
    
    for (var i = 0; i < values.length; i++) {
      if (values[i][0] == "") { targetRow = startRow + i; break; }
    }
    if (targetRow == -1) { targetRow = sheet.getLastRow() + 1; }

    var today = new Date();
    var targetRange = sheet.getRange(targetRow, 1, 1, 7); // 등록 시에는 G열까지만 씀
    
    targetRange.setValues([[
      today, data.tv_nick, data.tg_nick, data.uid, "등록요청", "", data.api_key
    ]]);
    
    targetRange.setHorizontalAlignment("center");
    sheet.getRange(targetRow, 1).setNumberFormat("yy년 MM월 dd일");

    return ContentService.createTextOutput(JSON.stringify({"result": "registered"})).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "message": err.toString()})).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}