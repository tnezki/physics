"""Regression tests for seven-row Physics Planner; run with python -m unittest discover -s planner/tests."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

PLANNER = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("physics_planner_test_module", PLANNER / "planner_server.py")
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)

class SevenRowAgenda(unittest.TestCase):
    def setUp(self):
        self.lessons = app.lesson_catalog()
        self.day = {"date":"2026-11-19","dow":"Thursday","display_date":"11/19","week_index":11,"control":"Regular Day","section":"", "day_number":0,"student_slots":["","","","",""],"custom_slots":[{"label":"","url":""}for _ in range(5)], "lesson_choice":"5.2.2", "lesson_custom":{}, "extra_rows":[{"label":"","url":""}for _ in range(4)]}
    def test_catalog_verified(self):
        self.assertTrue(self.lessons)
        self.assertTrue(all(item['student_url'].startswith('https://drive.google.com/file/d/') for item in self.lessons))
    def test_rows_and_teacher(self):
        rows,teacher=app.agenda_day_rows(self.day)
        self.assertEqual(len(rows),6)
        self.assertEqual(len([r for r in rows[2:] if r['label']]),0)
        self.assertIn('Live Vernier',rows[0]['label'])
        self.assertIn('student',rows[1]['kind']+'student')
        self.assertIn('drive.google.com',teacher['url'])
    def test_public_teacher_isolation(self):
        state={"days":[{**self.day,"dow":dow,"display_date":"11/19"}for dow in ('Mon','Tue','Wed','Thu','Fri')],"current_week_index":11}
        student=app.render_week(state,11,'current-week',True)
        teacher=app.render_teacher_week(state,11,'current-week',True)
        self.assertEqual(student.count('<tr'),7)
        self.assertEqual(teacher.count('<tr'),8)
        self.assertNotIn('1k07Vo1WDcaxNQzn7ZHZDJuhLlt0UPcV-',student)
        self.assertIn('1k07Vo1WDcaxNQzn7ZHZDJuhLlt0UPcV-',teacher)
    def test_invalid_lesson_rejected(self):
        self.day['lesson_choice']='nonexistent'
        with self.assertRaises(ValueError):app.validate_state({'days':[self.day]})

if __name__ == "__main__":unittest.main()
