import unittest


class AppEntrypointTests(unittest.TestCase):
    def test_streamlit_entrypoint_imports_without_model_call(self):
        import simulate_agent

        self.assertTrue(callable(simulate_agent.main))


if __name__ == "__main__":
    unittest.main()
