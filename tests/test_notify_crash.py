"""排程腳本 crash 通知:未捕捉例外 → Discord 警報(終結沉默失敗)。"""

import sys

from monitoring import notify


class TestAlertOnCrash:
    def _install_and_fire(self, monkeypatch, job="測試任務"):
        sent = []
        monkeypatch.setattr(notify, "send", sent.append)
        passthrough = []
        monkeypatch.setattr(sys, "__excepthook__",
                            lambda *a: passthrough.append(a))
        old_hook = sys.excepthook
        try:
            notify.alert_on_crash(job)
            err = RuntimeError("Yahoo 全數失敗")
            sys.excepthook(RuntimeError, err, None)
        finally:
            sys.excepthook = old_hook  # 不污染其他測試
        return sent, passthrough

    def test_uncaught_exception_sends_alert(self, monkeypatch):
        sent, _ = self._install_and_fire(monkeypatch, job="台股週掃")
        assert len(sent) == 1
        assert "台股週掃" in sent[0]
        assert "RuntimeError" in sent[0]
        assert "Yahoo 全數失敗" in sent[0]

    def test_original_excepthook_still_runs(self, monkeypatch):
        # 通知後必須續走預設 hook:traceback 照印、exit code 非 0
        _, passthrough = self._install_and_fire(monkeypatch)
        assert len(passthrough) == 1
