// What every UI test shares - the twin of the iOS MetalARMUITestCase:
// launching on the mock backend (or a live one), finding things by test tag,
// waiting for the UI to react, and screenshots.

package com.sreeram.metalarm

import android.graphics.Bitmap
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextReplacement
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Rule
import java.io.File

/** How long to wait for the UI to react - generous, returns the moment it does. */
const val REACTS = 20_000L

abstract class MetalArmUiTest {
    @get:Rule val compose = createEmptyComposeRule()
    private var scenario: ActivityScenario<MainActivity>? = null

    fun launch(config: TestConfig = TestConfig()) {
        AppGraph.testConfig = config
        AppGraph.reset()
        scenario = ActivityScenario.launch(MainActivity::class.java)
    }

    /** Signed in on the mock, past onboarding, Home loaded. */
    fun launchSignedIn(config: TestConfig = TestConfig()) {
        launch(config)
        waitForText("Level 14 · Intermediate")
    }

    @After fun tearDown() {
        scenario?.close()
        AppGraph.testConfig = null
        AppGraph.reset()
    }

    fun tag(tag: String): SemanticsNodeInteraction = compose.onNodeWithTag(tag, useUnmergedTree = true)

    fun exists(matcher: SemanticsMatcher): Boolean =
        compose.onAllNodes(matcher, useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()

    fun exists(tag: String) = exists(hasTestTag(tag))

    @OptIn(ExperimentalTestApi::class)
    fun waitFor(tag: String, timeout: Long = REACTS) = compose.waitUntil(timeout) { exists(tag) }

    fun waitForText(text: String, substring: Boolean = false, timeout: Long = REACTS) =
        compose.waitUntil(timeout) { exists(hasText(text, substring = substring)) }

    fun waitGone(tag: String, timeout: Long = REACTS) = compose.waitUntil(timeout) { !exists(tag) }

    fun text(text: String, substring: Boolean = false): SemanticsNodeInteraction =
        compose.onNode(hasText(text, substring = substring), useUnmergedTree = true)

    /** Scrolls a node into view (when it is in a scrolling column) and taps it. */
    fun tap(tag: String) {
        waitFor(tag)
        // A tap on a control that hasn't recomposed as enabled yet is
        // swallowed silently, and the test then fails somewhere else.
        compose.waitUntil(REACTS) { runCatching { tag(tag).assertIsEnabled() }.isSuccess }
        runCatching { tag(tag).performScrollTo() }
        tag(tag).performClick()
        compose.waitForIdle()
    }

    fun openTab(name: String) = tap("tab-${name.lowercase()}")

    fun type(tag: String, value: String) {
        waitFor(tag)
        tag(tag).performTextReplacement(value)
        compose.waitForIdle()
    }

    /** The current label of a text node by tag (its merged text). */
    fun textOf(tag: String): String {
        val config = tag(tag).fetchSemanticsNode().config
        config.getOrNull(SemanticsProperties.EditableText)?.let { return it.text }
        return config.getOrNull(SemanticsProperties.Text)?.joinToString("") { it.text } ?: ""
    }

    /** The whole screen, saved where scripts/android pulls screenshots from. */
    fun screenshot(name: String) {
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val bitmap = instrumentation.uiAutomation.takeScreenshot() ?: return
        val dir = File(instrumentation.targetContext.getExternalFilesDir(null), "screenshots").apply { mkdirs() }
        File(dir, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
