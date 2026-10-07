//
//  AppModel+Library.swift
//  MetalARM
//
//  The Library tab: ready-made programs and workouts for each training path.
//  Starting one copies it into a live session (Train takes over from there);
//  following a program keeps a place in its schedule, which the server moves
//  on when a workout from it is finished.
//

import Foundation

extension AppModel {
    func loadLibraryHome() async {
        await run("Couldn't load the Library") {
            libraryHome = try await api.libraryHome()
        }
    }

    /// One path's programs and workouts, with the current filters.
    func loadLibraryPath(_ category: String) async {
        await run("Couldn't load this path") {
            async let programs = api.libraryPrograms(category: category, filters: libraryFilters)
            async let workouts = api.libraryWorkouts(category: category, filters: libraryFilters)
            (libraryPrograms, libraryWorkouts) = try await (programs, workouts)
        }
    }

    func loadLibraryProgram(_ slug: String) async {
        if libraryProgram?.slug != slug { libraryProgram = nil }
        await run("Couldn't load this program") {
            libraryProgram = try await api.libraryProgram(slug: slug)
        }
    }

    func loadLibraryWorkout(_ slug: String) async {
        if libraryWorkout?.slug != slug { libraryWorkout = nil }
        await run("Couldn't load this workout") {
            libraryWorkout = try await api.libraryWorkout(slug: slug)
        }
    }

    /// Starts a Library workout as the live session. Returns true when it did,
    /// so the caller can switch to Train. One workout at a time: with one
    /// already going, nothing is replaced and the user is told why.
    @discardableResult
    func startLibraryWorkout(_ slug: String) async -> Bool {
        var started = false
        isBusy = true
        defer { isBusy = false }
        do {
            session = try await api.startLibraryWorkout(slug: slug)
            pendingExercises = []
            prHint = ""
            progressionHint = ""
            stopRestTimer()
            selectDefaultExercise()
            errorMessage = ""
            started = true
        } catch let error as APIError where error.status == 409 {
            errorMessage = "Finish or discard the workout you have going first."
        } catch APIError.signedOut {
            errorMessage = APIError.signedOut.localizedDescription
        } catch {
            errorMessage = "Couldn't start this workout: \(error.localizedDescription)"
        }
        return started
    }

    func saveLibraryWorkout(_ slug: String) async {
        await run("Couldn't save this workout") {
            let saved = try await api.saveLibraryWorkout(slug: slug)
            libraryNotice = "Saved \"\(saved.name)\" to your routines."
        }
    }

    func followProgram(_ slug: String) async {
        await run("Couldn't follow this program") {
            _ = try await api.followProgram(slug: slug)
            libraryProgram = try await api.libraryProgram(slug: slug)
            libraryHome = try await api.libraryHome()
        }
    }

    func unfollowProgram(_ slug: String) async {
        await run("Couldn't stop following this program") {
            _ = try await api.unfollowProgram(slug: slug)
            libraryProgram = try await api.libraryProgram(slug: slug)
            libraryHome = try await api.libraryHome()
        }
    }
}
