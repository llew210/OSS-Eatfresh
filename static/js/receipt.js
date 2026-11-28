// 영수증 등록 화면 스크립트 (업로드 화면 + 확인 화면 공용)
(function () {
  // ---------- 1) 업로드 화면: 선택한 사진 미리보기 ----------
  const fileInput = document.getElementById('receipt-file');
  if (fileInput) {
    const preview = document.getElementById('preview');
    const uploadText = document.getElementById('upload-text');
    const analyzeBtn = document.getElementById('analyze-btn');

    fileInput.addEventListener('change', function () {
      const file = fileInput.files[0];
      if (!file) {
        preview.hidden = true;
        uploadText.hidden = false;
        analyzeBtn.disabled = true;
        return;
      }
      preview.src = URL.createObjectURL(file);  // 브라우저 안에서만 만드는 미리보기 주소
      preview.hidden = false;
      uploadText.hidden = true;
      analyzeBtn.disabled = false;
    });

    document.getElementById('upload-form').addEventListener('submit', function () {
      analyzeBtn.textContent = '분석 중...';  // OCR은 몇 초 걸릴 수 있음
      analyzeBtn.disabled = true;
    });
  }

  // ---------- 2) 확인 화면 ----------
  const list = document.getElementById('item-list');
  if (!list) return;

  const form = document.getElementById('review-form');
  const template = document.getElementById('row-template');
  const saveBtn = document.getElementById('save-btn');
  const status = document.getElementById('save-status');

  function pendingCount() {
    return Array.from(list.querySelectorAll('.item')).filter(function (li) {
      return li.dataset.low === '1' && li.querySelector('[name=confirmed]').value !== '1';
    }).length;
  }

  function refresh() {
    const rows = list.querySelectorAll('.item').length;
    const pending = pendingCount();
    saveBtn.disabled = pending > 0;
    status.classList.toggle('warn', pending > 0);
    if (rows === 0) {
      status.textContent = '등록할 품목이 없어요. 품목을 추가해 주세요.';
    } else if (pending > 0) {
      status.textContent = '확인이 필요한 품목 ' + pending + '개가 남아 있어요.';
    } else {
      status.textContent = '모든 품목을 확인했어요.';
    }
  }

  function setConfirmed(li, on) {
    li.querySelector('[name=confirmed]').value = on ? '1' : '0';
    li.classList.toggle('confirmed', on);
    const box = li.querySelector('.confirm-box');
    if (box) box.checked = on;
  }

  function addRow() {
    const li = template.content.firstElementChild.cloneNode(true);
    list.appendChild(li);
    li.querySelector('[name=name]').focus();
    refresh();
  }

  list.addEventListener('change', function (e) {
    const li = e.target.closest('.item');
    if (!li) return;
    if (e.target.classList.contains('confirm-box')) {
      setConfirmed(li, e.target.checked);
    } else if (li.dataset.low === '1' && (e.target.name === 'name' || e.target.name === 'quantity')) {
      setConfirmed(li, true);  // 사용자가 직접 고쳤다면 확인한 것으로 본다
    }
    refresh();
  });

  list.addEventListener('click', function (e) {
    const li = e.target.closest('.item');
    if (!li) return;
    if (e.target.classList.contains('remove')) {
      li.remove();
    } else if (e.target.classList.contains('chip')) {
      li.querySelector('[name=name]').value = e.target.dataset.name;  // 후보 이름 선택
      setConfirmed(li, true);
    } else {
      return;
    }
    refresh();
  });

  document.getElementById('add-row').addEventListener('click', addRow);

  form.addEventListener('submit', function (e) {
    // Enter 키 등으로 버튼을 거치지 않고 제출되는 경우도 막는다
    if (pendingCount() > 0 || list.querySelectorAll('.item').length === 0) {
      e.preventDefault();
      refresh();
    }
  });

  if (list.querySelectorAll('.item').length === 0) addRow();  // 직접 입력: 빈 줄 하나로 시작
  refresh();
})();