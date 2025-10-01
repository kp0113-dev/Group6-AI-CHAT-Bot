import unittest

from lambdas.charger_gpt import nlu


class TestNLUHelpers(unittest.TestCase):
    def test_is_valid_course_code(self):
        valid = ["CS101", "ECE-301", "MATH 201", "CPE399A", "bio-110"]
        invalid = ["library", "it", "who", "123", "CS10", "CS10100", "", None]
        for v in valid:
            self.assertTrue(nlu.is_valid_course_code(v), f"Expected valid: {v}")
        for v in invalid:
            self.assertFalse(nlu.is_valid_course_code(v), f"Expected invalid: {v}")

    def test_resolve_pronoun_referent_building(self):
        session_attrs = {"last_building_name": "Library", "last_intent": "GetCampusLocationIntent"}
        self.assertEqual(nlu.resolve_pronoun_referent("When is it open?", session_attrs), "building")
        self.assertEqual(nlu.resolve_pronoun_referent("Where is it?", session_attrs), "building")

    def test_resolve_pronoun_referent_course(self):
        session_attrs = {"last_course_code": "ECE301", "last_intent": "GetClassScheduleIntent"}
        self.assertEqual(nlu.resolve_pronoun_referent("When is it?", session_attrs), "course")
        self.assertEqual(nlu.resolve_pronoun_referent("Who teaches it?", session_attrs), "course")


if __name__ == "__main__":
    unittest.main()
