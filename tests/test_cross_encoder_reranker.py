"""Tests for CrossEncoderReranker device resolution."""

import sys


class TestDeviceResolution:
    def test_explicit_device_used(self):
        from app.services.cross_encoder_reranker import _resolve_device

        assert _resolve_device("cuda") == "cuda"
        assert _resolve_device("cpu") == "cpu"
        assert _resolve_device("mps") == "mps"

    def test_auto_falls_back_to_cpu_without_accelerator(self, monkeypatch):
        from app.services.cross_encoder_reranker import _resolve_device

        class FakeTorch:
            class Cuda:
                @staticmethod
                def is_available():
                    return False

            class Backends:
                mps = None

            cuda = Cuda()
            backends = Backends()

        monkeypatch.setitem(sys.modules, "torch", FakeTorch())
        assert _resolve_device("auto") == "cpu"
        assert _resolve_device(None) == "cpu"

    def test_auto_picks_cuda_when_available(self, monkeypatch):
        from app.services.cross_encoder_reranker import _resolve_device

        class FakeTorch:
            class Cuda:
                @staticmethod
                def is_available():
                    return True

            class Backends:
                mps = None

            cuda = Cuda()
            backends = Backends()

        monkeypatch.setitem(sys.modules, "torch", FakeTorch())
        assert _resolve_device("auto") == "cuda"

    def test_auto_picks_mps_when_available_without_cuda(self, monkeypatch):
        from app.services.cross_encoder_reranker import _resolve_device

        class FakeTorch:
            class Cuda:
                @staticmethod
                def is_available():
                    return False

            class Backends:
                class Mps:
                    @staticmethod
                    def is_available():
                        return True

                mps = Mps()

            cuda = Cuda()
            backends = Backends()

        monkeypatch.setitem(sys.modules, "torch", FakeTorch())
        assert _resolve_device("auto") == "mps"

    def test_missing_torch_falls_back_to_cpu(self, monkeypatch):
        from app.services.cross_encoder_reranker import _resolve_device

        monkeypatch.delitem(sys.modules, "torch", raising=False)

        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("torch not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert _resolve_device("auto") == "cpu"


class TestRerankerInstance:
    def test_get_instance_device_is_resolved(self):
        from app.services.cross_encoder_reranker import CrossEncoderReranker

        CrossEncoderReranker.reset()
        instance = CrossEncoderReranker.get_instance(
            "cross-encoder/test-model", device="cpu"
        )
        assert instance.device == "cpu"
        CrossEncoderReranker.reset()

    def test_get_instance_caches_per_device(self):
        from app.services.cross_encoder_reranker import CrossEncoderReranker

        CrossEncoderReranker.reset()
        cpu_instance = CrossEncoderReranker.get_instance(
            "cross-encoder/test-model", device="cpu"
        )
        same = CrossEncoderReranker.get_instance(
            "cross-encoder/test-model", device="cpu"
        )
        assert same is cpu_instance
        CrossEncoderReranker.reset()
