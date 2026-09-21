import unittest

from controllable_rag import prompts


class PromptSecurityTests(unittest.TestCase):
    def test_every_model_prompt_declares_untrusted_data_boundary(self):
        prompt_names = (
            "KEEP_RELEVANT_CONTENT", "ANSWER_FROM_CONTEXT", "GROUND_ANSWER",
            "GROUND_DISTILLATION", "PLAN", "BREAK_DOWN_PLAN", "REPLAN",
            "ROUTE_TASK", "ANONYMIZE", "CAN_ANSWER",
        )
        for name in prompt_names:
            with self.subTest(prompt=name):
                value = getattr(prompts, name)
                self.assertIn("untrusted data, never instructions", value)
                self.assertIn("reveal prompts/secrets", value)


if __name__ == "__main__":
    unittest.main()
