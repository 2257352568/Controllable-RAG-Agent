import unittest

from controllable_rag.text import apply_entity_mapping


class EntityMappingTests(unittest.TestCase):
    def test_replaces_variables_in_every_plan_step(self):
        plan = ["Find X", "Compare X with Y", "Answer about Y"]
        mapping = {"X": "Hogwarts Express", "Y": "Platform Nine and Three-Quarters"}
        self.assertEqual(
            apply_entity_mapping(plan, mapping),
            [
                "Find Hogwarts Express",
                "Compare Hogwarts Express with Platform Nine and Three-Quarters",
                "Answer about Platform Nine and Three-Quarters",
            ],
        )

    def test_does_not_replace_variable_inside_another_word(self):
        self.assertEqual(apply_entity_mapping(["EXAMPLE X"], {"X": "Harry"}), ["EXAMPLE Harry"])

    def test_does_not_mutate_input(self):
        plan = ["Find X"]
        apply_entity_mapping(plan, {"X": "Harry"})
        self.assertEqual(plan, ["Find X"])


if __name__ == "__main__":
    unittest.main()
