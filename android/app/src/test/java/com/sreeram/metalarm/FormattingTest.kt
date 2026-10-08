package com.sreeram.metalarm

import com.sreeram.metalarm.api.Motivation
import com.sreeram.metalarm.api.PREvent
import com.sreeram.metalarm.api.RankTitle
import com.sreeram.metalarm.api.WeightUnit
import com.sreeram.metalarm.api.celebrated
import com.sreeram.metalarm.api.formatNumber
import com.sreeram.metalarm.api.initials
import com.sreeram.metalarm.api.parseServerDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class FormattingTest {
    @Test fun numbersPrintLikeTheBackend() {
        assertEquals("85", formatNumber(85.0))
        assertEquals("82.5", formatNumber(82.5))
        assertEquals("142.25", formatNumber(142.25))
        assertEquals("0", formatNumber(0.0))
    }

    @Test fun poundsShowOneDecimal() {
        assertEquals("176.4 lb", WeightUnit.Lb.format(80.0))
        assertEquals("80 kg", WeightUnit.Kg.format(80.0))
    }

    @Test fun firstEverLogsAreNotCelebrated() {
        val baseline = PREvent("e", "Bench", "max_weight", 60.0, isBaseline = true)
        assertNull(listOf(baseline).celebrated)
        assertNotNull(listOf(baseline, baseline.copy(isBaseline = false)).celebrated)
    }

    @Test fun repRecordsReadAsReps() {
        val reps = PREvent("e", "Bench", "max_reps_at_weight", 8.0, weightKg = 80.0)
        assertEquals("New rep record on Bench: 8 reps at 80 kg", reps.headline(WeightUnit.Kg))
    }

    @Test fun serverTimestampsParse() {
        assertNotNull(parseServerDate("2026-09-13T18:05:12.482311Z"))
        assertNotNull(parseServerDate("2026-09-07T00:00:00+05:30"))
    }

    @Test fun initialsUseFirstTwoWords() {
        assertEquals("SR", initials("Sree Ram"))
        assertEquals("M", initials("Meera"))
    }

    @Test fun ranksReadAsTiers() {
        assertEquals("Intermediate", RankTitle.of("c"))
        assertEquals("Advanced, Elite and World Class", RankTitle.list(listOf("B", "A", "S")))
    }

    @Test fun theLineMatchesTheOtherApps() {
        // sum of code points % 14, the same as Motivation.swift and the web.
        val key = "abc"
        assertEquals(Motivation.lines[(97 + 98 + 99) % Motivation.lines.size], Motivation.line(key))
    }
}
