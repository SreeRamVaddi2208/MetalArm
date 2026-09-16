//
//  ContractFixtures.swift
//  MetalARM
//
//  Example payloads in the exact shapes of backend/app/schemas (values taken
//  from docs/workouts-api.md where it gives them). Used by MockAPIClient for
//  previews and UI tests, and by the decoding unit tests.
//

enum ContractFixtures {
    static let userID = "7d1c2b3a-5e6f-4a8b-9c0d-000000000001"
    static let benchID = "0b6f7c1e-1111-4a8e-9c1a-000000000001"
    static let squatID = "0b6f7c1e-1111-4a8e-9c1a-000000000002"
    static let deadliftID = "0b6f7c1e-1111-4a8e-9c1a-000000000003"
    static let pressID = "0b6f7c1e-1111-4a8e-9c1a-000000000004"
    static let rowID = "0b6f7c1e-1111-4a8e-9c1a-000000000005"
    static let pullUpID = "0b6f7c1e-1111-4a8e-9c1a-000000000006"
    static let sessionID = "3c3c3c3c-2222-4b4b-8a8a-000000000001"
    static let previousSessionID = "3c3c3c3c-2222-4b4b-8a8a-000000000000"
    static let partyID = "5a5a5a5a-3333-4c4c-9d9d-000000000001"

    static let tokens = """
    {"access_token": "access-1", "token_type": "bearer", "expires_in": 3600, "refresh_token": "refresh-1", "refresh_expires_in": 2592000}
    """

    static let progress = """
    {"total_xp": 18450, "current_level": 14, "points_balance": 640, "longest_streak": 12, "last_completed_on": "2026-09-12",
     "xp_into_level": 2140, "xp_for_next_level": 3000, "current_streak": 6, "streak_is_active": true,
     "rank": "C", "rank_by_level": "C", "next_rank": "B", "next_rank_level": 20, "next_rank_streak": null,
     "next_rank_trial": "Barbell Bench Press at 1x bodyweight", "trials_passed": ""}
    """

    static let me = """
    {"id": "\(userID)", "email": "sree@metalarm.dev", "display_name": "Sree Ram", "timezone": "Asia/Kolkata",
     "created_at": "2026-09-01T10:00:00.123456Z", "weight_unit": "kg", "progress": \(progress)}
    """

    static func exercise(_ id: String, _ name: String, _ muscles: [String], equipment: String = "barbell") -> String {
        let groups = muscles.map { "\"\($0)\"" }.joined(separator: ", ")
        return """
        {"id": "\(id)", "name": "\(name)", "slug": null, "category": "strength", "primary_muscle_groups": [\(groups)],
         "equipment": "\(equipment)", "instructions": null, "media_url": null, "is_custom": false, "is_archived": false}
        """
    }

    static let bench = exercise(benchID, "Barbell Bench Press", ["chest", "triceps", "shoulders"])

    static let exercises = "[" + [
        bench,
        exercise(squatID, "Barbell Back Squat", ["quads", "glutes", "core"]),
        exercise(deadliftID, "Conventional Deadlift", ["hamstrings", "glutes", "back"]),
        exercise(pressID, "Overhead Press", ["shoulders", "triceps"]),
        exercise(rowID, "Barbell Row", ["back", "biceps"]),
        exercise(pullUpID, "Pull-Up", ["back", "biceps"], equipment: "bodyweight"),
    ].joined(separator: ",") + "]"

    static func set(id: String, session: String = sessionID, exercise: String = benchID, number: Int, weightKg: Double, reps: Int, isPR: Bool = false) -> String {
        """
        {"id": "\(id)", "session_id": "\(session)", "exercise_id": "\(exercise)", "set_number": \(number), "weight_kg": \(weightKg),
         "reps": \(reps), "rpe": null, "is_warmup": false, "is_pr": \(isPR), "duration_seconds": null, "distance_m": null,
         "completed_at": "2026-09-13T18:05:12.482311Z"}
        """
    }

    static let benchPreviousSets = "[" + [
        set(id: "9a9a9a9a-0000-4000-8000-000000000001", session: previousSessionID, number: 1, weightKg: 80, reps: 8),
        set(id: "9a9a9a9a-0000-4000-8000-000000000002", session: previousSessionID, number: 2, weightKg: 80, reps: 7),
    ].joined(separator: ",") + "]"

    static let lastPerformance = """
    {"exercise_id": "\(benchID)", "session_id": "\(previousSessionID)", "performed_at": "2026-09-10T18:00:00Z", "sets": \(benchPreviousSets),
     "hint": {"kind": "progress", "text": "Try 87.5 kg x 5", "target_weight_kg": 87.5, "target_reps": 5}}
    """

    static let activeSession = """
    {"session": {"id": "\(sessionID)", "name": null, "status": "in_progress", "routine_id": null,
     "started_at": "2026-09-13T18:00:00.000001Z", "ended_at": null, "duration_seconds": 1260, "working_sets": 1,
     "total_volume_kg": 680.0, "points_total": 52, "points_credited": 0, "qualified": null,
     "exercises": [{"exercise": \(bench), "target": {"target_sets": 3, "target_reps": 8, "target_weight_kg": 85.0, "rest_seconds": 120},
                    "sets": [\(set(id: "9b9b9b9b-0000-4000-8000-000000000001", number: 1, weightKg: 85, reps: 8, isPR: true))],
                    "previous_sets": \(benchPreviousSets)}]}}
    """

    static let noActiveSession = """
    {"session": null}
    """

    static let progression = """
    {"xp_awarded": 52, "points_awarded": 52, "total_xp": 1840, "level_before": 9, "level_after": 10,
     "rank_before": "D", "rank_after": "D", "current_streak": 3, "longest_streak": 5, "leveled_up": true, "ranked_up": false}
    """

    static let setLogResult = """
    {"set": \(set(id: "9b9b9b9b-0000-4000-8000-000000000002", number: 2, weightKg: 110, reps: 5, isPR: true)),
     "pr_events": [
       {"exercise_id": "\(benchID)", "exercise_name": "Barbell Bench Press", "record_type": "max_weight", "value": 110.0,
        "weight_kg": 110.0, "previous_value": 100.0, "is_baseline": false, "bonus_awarded": true, "set_id": null},
       {"exercise_id": "\(benchID)", "exercise_name": "Barbell Bench Press", "record_type": "est_1rm", "value": 128.33,
        "weight_kg": null, "previous_value": 116.67, "is_baseline": false, "bonus_awarded": false, "set_id": null}],
     "awards": [{"source_type": "set_logged", "points": 2, "reason": "Set logged"},
                {"source_type": "pr_achieved", "points": 50, "reason": "New PR: max_weight"}],
     "points_awarded": 52, "session_points": 66, "set_cap_reached": false, "progression": \(progression), "is_duplicate": false}
    """

    static let streak = """
    {"weeks": 2, "this_week_sessions": 2, "target": 3, "this_week_done": false, "sessions_to_go": 1}
    """

    static let finishResult = """
    {"session": {"id": "\(sessionID)", "name": null, "status": "completed", "started_at": "2026-09-13T18:00:00Z",
                 "ended_at": "2026-09-13T18:58:00Z", "duration_seconds": 3480, "working_sets": 18, "exercise_count": 4,
                 "total_volume_kg": 9120.0, "points_total": 140, "pr_count": 2},
     "qualified": true,
     "awards": [{"source_type": "session_completed", "points": 36, "reason": "Workout completed"},
                {"source_type": "streak_bonus", "points": 20, "reason": "2-week streak"}],
     "breakdown": {"set_points": 36, "pr_bonus": 50, "session_bonus": 36, "streak_bonus": 20, "reversals": -2, "total": 140},
     "points_credited": 140, "pr_events": [], "streak": \(streak), "progression": \(progression)}
    """

    static let points = """
    {"total_points": 3120, "this_week_points": 185, "sessions_completed": 142, "streak": \(streak)}
    """

    static let history = """
    [{"session_id": "a1", "performed_at": "2026-06-02T18:00:00Z", "top_weight_kg": 72.5, "top_weight_reps": 8, "best_est_1rm": 91.8, "volume_kg": 4200.0, "working_sets": 12, "total_reps": 96},
     {"session_id": "a2", "performed_at": "2026-07-01T18:00:00Z", "top_weight_kg": 77.5, "top_weight_reps": 6, "best_est_1rm": 93.0, "volume_kg": 4650.0, "working_sets": 12, "total_reps": 90},
     {"session_id": "a3", "performed_at": "2026-08-05T18:00:00Z", "top_weight_kg": 80.0, "top_weight_reps": 8, "best_est_1rm": 101.3, "volume_kg": 5100.0, "working_sets": 13, "total_reps": 98},
     {"session_id": "a4", "performed_at": "2026-09-10T18:00:00Z", "top_weight_kg": 85.0, "top_weight_reps": 7, "best_est_1rm": 104.83, "volume_kg": 5440.0, "working_sets": 14, "total_reps": 101}]
    """

    static let records = """
    [{"exercise_id": "\(benchID)", "exercise_name": "Barbell Bench Press", "record_type": "max_weight", "value": 85.0, "weight_kg": 85.0, "achieved_at": "2026-09-10T18:20:00Z", "session_id": "a4", "set_id": null},
     {"exercise_id": "\(benchID)", "exercise_name": "Barbell Bench Press", "record_type": "est_1rm", "value": 104.83, "weight_kg": 85.0, "achieved_at": "2026-09-10T18:20:00Z", "session_id": "a4", "set_id": null},
     {"exercise_id": "\(benchID)", "exercise_name": "Barbell Bench Press", "record_type": "max_reps_at_weight", "value": 8.0, "weight_kg": 80.0, "achieved_at": "2026-08-05T18:20:00Z", "session_id": "a3", "set_id": null},
     {"exercise_id": "\(squatID)", "exercise_name": "Barbell Back Squat", "record_type": "max_weight", "value": 122.5, "weight_kg": 122.5, "achieved_at": "2026-08-26T18:20:00Z", "session_id": "b1", "set_id": null}]
    """

    static let parties = """
    [{"id": "\(partyID)", "name": "Iron Crew", "owner_id": "\(userID)", "max_members": 10, "member_count": 5, "is_active": true,
      "created_at": "2026-09-02T10:00:00Z", "my_role": "owner", "invite_code": "IRON2345", "total_party_xp": 9120}]
    """

    static let partyBoard = """
    {"party_id": "\(partyID)", "period": "week", "period_start": "2026-09-07T00:00:00+05:30", "entries": [
      {"position": 1, "user_id": "\(userID)", "display_name": "Sree Ram", "points": 3120, "workouts": 4, "level": 14, "rank": "C", "is_me": true},
      {"position": 2, "user_id": "u2", "display_name": "Meera", "points": 2840, "workouts": 4, "level": 13, "rank": "C", "is_me": false},
      {"position": 3, "user_id": "u3", "display_name": "Arjun", "points": 2605, "workouts": 3, "level": 12, "rank": "D", "is_me": false},
      {"position": 4, "user_id": "u4", "display_name": "Divya", "points": 2340, "workouts": 3, "level": 11, "rank": "D", "is_me": false}]}
    """

    static let partyRaid = """
    {"party_id": "\(partyID)", "week_key": "2026-W38", "name": "Iron Golem", "max_hp": 60000, "hp_remaining": 41250,
     "damage_dealt": 21750, "healed": 3000, "idle_days": 1, "defeated": false, "defeated_at": null,
     "ends_at": "2026-09-21T00:00:00Z", "hitters": [
      {"user_id": "\(userID)", "display_name": "Sree Ram", "damage": 9200, "hits": 3, "is_me": true},
      {"user_id": "u2", "display_name": "Meera", "damage": 7400, "hits": 2, "is_me": false},
      {"user_id": "u3", "display_name": "Arjun", "damage": 5150, "hits": 2, "is_me": false}]}
    """

    static let importResult = """
    {"source": "strong", "workouts_imported": 42, "sets_imported": 610, "workouts_skipped": 3, "rows_skipped": 2,
     "exercises_created": ["Cable Kickback (Cable)"], "xp_awarded": 420, "duplicate": false, "progression": \(progression)}
    """

    static let rankTrials = """
    [{"rank": "B", "lift": "Barbell Bench Press", "description": "Barbell Bench Press at 1x bodyweight", "multiplier": 1.0,
      "target_kg": 80.0, "best_kg": 72.5, "passed": false},
     {"rank": "A", "lift": "Back Squat", "description": "Back Squat at 1.5x bodyweight", "multiplier": 1.5,
      "target_kg": 120.0, "best_kg": 100.0, "passed": false},
     {"rank": "S", "lift": "Deadlift", "description": "Deadlift at 2x bodyweight", "multiplier": 2.0,
      "target_kg": 160.0, "best_kg": null, "passed": false}]
    """

    static let profile = """
    {"user": {"id": "\(userID)", "email": "sree@metalarm.dev", "display_name": "Sree Ram", "timezone": "Asia/Kolkata", "created_at": "2026-09-01T10:00:00Z", "weight_unit": "kg"},
     "progress": \(progress),
     "stats": {"quests_completed": 57, "party_quests_completed": 9, "rewards_redeemed": 3, "points_earned": 4200, "points_spent": 1080,
               "parties_joined": 1, "party_xp_contributed": 2140, "member_since": "2026-09-01T10:00:00Z",
               "workouts_completed": 142, "workout_prs": 23, "total_volume_kg": 512340.0, "longest_workout_streak": 6},
     "badges": [
       {"id": "first_workout", "name": "First Workout", "description": "Finish a workout", "icon": "dumbbell", "earned": true, "progress": 1, "target": 1, "percent": 100},
       {"id": "first_pr", "name": "First PR", "description": "Beat a record", "icon": "trophy", "earned": true, "progress": 1, "target": 1, "percent": 100},
       {"id": "ten_workouts", "name": "10 Workouts", "description": "Finish 10 workouts", "icon": "flame", "earned": true, "progress": 10, "target": 10, "percent": 100},
       {"id": "workout_streak_4", "name": "4-Week Streak", "description": "Hit your weekly target 4 weeks running", "icon": "calendar", "earned": false, "progress": 2, "target": 4, "percent": 50}],
     "badges_earned": 3, "badges_total": 4}
    """
}
