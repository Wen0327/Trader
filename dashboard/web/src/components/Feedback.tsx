export function ErrorBox({ msg }: { msg: string }) {
  return <p className="error">API 錯誤:{msg}(確認 uvicorn 是否啟動)</p>;
}

export function Loading() {
  return <p className="muted">載入中…</p>;
}

export function Empty({ msg }: { msg: string }) {
  return <p className="muted">{msg}</p>;
}

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="info-tip" tabIndex={0}>
      ⓘ
      <span className="info-tip-bubble">{text}</span>
    </span>
  );
}
