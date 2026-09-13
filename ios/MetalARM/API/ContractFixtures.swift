//
//  ContractFixtures.swift
//  MetalARM
//
//  The example payloads from API_CONTRACT.md, verbatim. Used by MockAPIClient
//  (previews and UI tests) and by the decoding unit tests.
//

enum ContractFixtures {
    static let user = """
    {"id": 1, "name": "Sree Ram", "level": 14, "level_name": "Forged", "xp_current": 2140, "xp_to_next_level": 3000, "streak_days": 6}
    """

    // The contract shows bench only; squat and deadlift (the other two Progress tabs)
    // use the ids backend/app/seed.py gives them.
    static let exercises = """
    [
      {"id": 1, "name": "Barbell Bench Press", "category": "strength", "muscle_groups": ["chest", "triceps"], "equipment": "barbell"},
      {"id": 2, "name": "Incline Dumbbell Press", "category": "strength", "muscle_groups": ["chest", "shoulders"], "equipment": "dumbbell"},
      {"id": 3, "name": "Barbell Back Squat", "category": "strength", "muscle_groups": ["quads", "glutes", "core"], "equipment": "barbell"},
      {"id": 5, "name": "Conventional Deadlift", "category": "strength", "muscle_groups": ["hamstrings", "glutes", "back"], "equipment": "barbell"}
    ]
    """

    static let sessionStart = """
    {"id": 501, "user_id": 1, "started_at": "2026-09-10T18:02:00Z", "status": "in_progress"}
    """

    static let logSetWithPR = """
    {
      "set": {"id": 9001, "session_id": 501, "exercise_id": 1, "set_number": 3, "weight_kg": 85, "reps": 6, "is_warmup": false, "is_pr": true},
      "pr": {"record_type": "max_weight", "value": 85, "previous_value": 82.5},
      "points_awarded": 2
    }
    """

    static let workoutSummary = """
    {
      "duration_min": 48, "total_volume_kg": 6420, "total_sets": 18,
      "points_breakdown": {"sets": 36, "session_completed": 25, "pr_bonus": 50, "streak_bonus": 74},
      "total_points": 185,
      "new_prs": [{"exercise_name": "Barbell Bench Press", "record_type": "max_weight", "value": 85, "reps": 7}],
      "level": {"level": 14, "level_name": "Forged", "xp_current": 2140, "xp_to_next_level": 3000, "leveled_up": false}
    }
    """

    static let progress = """
    {
      "exercise_name": "Barbell Bench Press", "metric": "max_weight", "unit": "kg",
      "current_value": 85, "change_since_start": 12.5,
      "points": [{"date": "2026-01-05", "value": 72.5}, {"date": "2026-04-14", "value": 77.5}, {"date": "2026-06-30", "value": 80}, {"date": "2026-09-08", "value": 85}]
    }
    """

    static let records = """
    [
      {"record_type": "max_weight", "label": "Heaviest", "value": 85, "unit": "kg", "detail": "85 kg × 7 reps", "achieved_at": "2026-09-08"},
      {"record_type": "est_1rm", "label": "Best est. 1RM", "value": 142, "unit": "kg", "detail": "142 kg", "achieved_at": "2026-08-29"}
    ]
    """

    static let leaderboard = """
    [
      {"rank": 1, "user_id": 1, "name": "Sree Ram", "points": 3120, "is_current_user": true},
      {"rank": 2, "user_id": 2, "name": "Meera", "points": 2840, "is_current_user": false},
      {"rank": 3, "user_id": 3, "name": "Arjun", "points": 2605, "is_current_user": false},
      {"rank": 4, "user_id": 4, "name": "Divya", "points": 2340, "is_current_user": false, "streak_days": 5}
    ]
    """

    static let profile = """
    {
      "user": {"id": 1, "name": "Sree Ram", "level": 14, "level_name": "Forged", "xp_current": 2140, "xp_to_next_level": 3000},
      "stats": {"workouts": 142, "streak_days": 6, "prs_set": 23},
      "badges": [{"id": "gold-1", "name": "First PR", "earned": true}, {"id": "streak-7", "name": "7-Day Streak", "earned": false}]
    }
    """

    static let friendActivity = """
    [
      {"user_name": "Arjun", "text": "hit a new PR on Bench Press", "hours_ago": 2},
      {"user_name": "Meera", "text": "reached a 12-day streak", "hours_ago": 5}
    ]
    """
}
