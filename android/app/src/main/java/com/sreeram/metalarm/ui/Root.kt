// The app's frame - the twin of the iOS RootView. Onboarding, then sign-in,
// then the training-path question (asked once), then five tabs: Home, Train,
// Library, Progress, Profile. Each tab keeps its own back stack, so a list
// pushes its detail and the system back gesture works per tab. The workout
// summary covers everything when a workout finishes.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.outlined.AddCircleOutline
import androidx.compose.material.icons.outlined.PersonOutline
import androidx.compose.material.icons.outlined.Search
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import com.sreeram.metalarm.theme.LocalTabBarInset
import com.sreeram.metalarm.theme.ScreenTitle
import com.sreeram.metalarm.ui.library.SavedLibrary
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.LibraryBooks
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.rememberNavController
import com.sreeram.metalarm.AppGraph
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.ui.library.LibraryTab

enum class AppTab(val label: String, val icon: ImageVector) {
    Home("Home", Icons.Outlined.Home),
    Explore("Explore", Icons.Outlined.Search),
    Workout("Workout", Icons.Outlined.AddCircleOutline),
    Library("Library", Icons.AutoMirrored.Outlined.LibraryBooks),
    You("You", Icons.Outlined.PersonOutline),
}

/** Material components (switches, sheets, menus) drawn in our tokens. */
@Composable
fun MetalArmTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Theme.accent, onPrimary = Theme.onAccent, background = Theme.bg, onBackground = Theme.text,
            surface = Theme.surface, onSurface = Theme.text, surfaceVariant = Theme.surface2,
            onSurfaceVariant = Theme.text2, outline = Theme.border, error = Theme.danger,
            surfaceContainer = Theme.surface, surfaceContainerHigh = Theme.surface2,
            surfaceContainerHighest = Theme.surface2, surfaceContainerLow = Theme.surface,
        ),
        content = content,
    )
}

@Composable
fun RootScreen(model: AppModel) {
    val context = LocalContext.current
    var onboarded by remember { mutableStateOf(AppGraph.hasOnboarded(context)) }
    var authSignUp by rememberSaveable { mutableStateOf(true) }
    // Answered (or skipped) in this launch: `me` refreshes a beat later, so
    // without this the question could flash back before the server replies.
    var pathAsked by rememberSaveable { mutableStateOf(false) }

    MetalArmTheme {
        Box(Modifier.fillMaxSize().background(Theme.bg)) {
            when {
                !onboarded -> OnboardingScreen { signUp ->
                    authSignUp = signUp
                    AppGraph.setOnboarded(context)
                    onboarded = true
                }
                !model.isSignedIn -> AuthScreen(model, signUp = authSignUp, onToggle = { authSignUp = !authSignUp })
                model.needsTrainingPath && !pathAsked -> TrainingPathScreen(model, isOnboarding = true) { pathAsked = true }
                else -> Tabs(model)
            }
        }
    }
}

@Composable
private fun Tabs(model: AppModel) {
    var selected by rememberSaveable { mutableStateOf(AppTab.Home) }
    val controllers: Map<AppTab, NavHostController> = AppTab.entries.associateWith { rememberNavController() }
    val saveable = rememberSaveableStateHolder()

    // `me` arrives with Home; the path question depends on it.
    LaunchedEffect(Unit) { model.loadHome() }

    // Back on a tab's root goes Home first, like most Android apps.
    BackHandler(enabled = selected != AppTab.Home && controllers.getValue(selected).previousBackStackEntry == null) {
        selected = AppTab.Home
    }

    Box(Modifier.fillMaxSize().background(Theme.bg)) {
        CompositionLocalProvider(LocalTabBarInset provides TabBarInset) {
            saveable.SaveableStateProvider(selected.name) {
                val nav = controllers.getValue(selected)
                when (selected) {
                    AppTab.Home -> HomeTab(model, nav, onOpenWorkout = { selected = AppTab.Workout })
                    AppTab.Explore -> LibraryTab(model, nav, onStarted = { selected = AppTab.Workout })
                    AppTab.Workout -> WorkoutScreen(model, onOpenLibrary = { selected = AppTab.Explore })
                    AppTab.Library -> SavedLibrary(model, onStarted = { selected = AppTab.Workout })
                    AppTab.You -> YouTab(model, nav)
                }
            }
        }
        FloatingTabBar(selected, Modifier.align(Alignment.BottomCenter)) { tab ->
            if (tab == selected) {
                // A second tap returns the tab to its root.
                controllers.getValue(tab).takeIf { it.currentBackStackEntry != null }?.let { it.popBackStack(it.graph.startDestinationId, false) }
            }
            selected = tab
        }

        val result = model.finishResult
        if (model.showingSummary && result != null) {
            SummaryScreen(result, model.weightUnit, model.shareInviteCode) { model.showingSummary = false }
        }
    }
}

private val TabBarHeight = 68.dp
private val TabBarInset = TabBarHeight + 24.dp

/** The five tabs, in a pill that floats over the content. */
@Composable
private fun FloatingTabBar(selected: AppTab, modifier: Modifier = Modifier, onSelect: (AppTab) -> Unit) {
    Row(
        modifier
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = Theme.gutter, vertical = Theme.Space.s8)
            .fillMaxWidth()
            .height(TabBarHeight)
            .background(Theme.surface2.copy(alpha = 0.92f), CircleShape)
            .border(1.dp, Theme.border, CircleShape)
            .padding(Theme.Space.s4),
    ) {
        AppTab.entries.forEach { tab ->
            Column(
                Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clip(CircleShape)
                    .background(if (tab == selected) Theme.bg else Color.Transparent)
                    .selectable(selected = tab == selected, role = Role.Tab) { onSelect(tab) }
                    .testTag("tab-${tab.name.lowercase()}"),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Icon(tab.icon, contentDescription = null, tint = Theme.text)
                Text(tab.label, style = Theme.caption, color = Theme.text, maxLines = 1)
            }
        }
    }
}

/** The You tab: your progress and your profile, one switch apart. */
@Composable
private fun YouTab(model: AppModel, nav: NavHostController) {
    var part by rememberSaveable { mutableStateOf("Progress") }
    Column(Modifier.fillMaxSize().background(Theme.bg).windowInsetsPadding(WindowInsets.statusBars)) {
        Column(Modifier.padding(horizontal = Theme.gutter), verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
            ScreenTitle("You")
            Row(Modifier.fillMaxWidth().background(Theme.surface, RoundedCornerShape(Theme.radius)).padding(Theme.Space.s4)) {
                listOf("Progress", "Profile").forEach { option ->
                    Box(
                        Modifier
                            .weight(1f)
                            .heightIn(min = Theme.touch)
                            .clip(RoundedCornerShape(Theme.radius))
                            .background(if (part == option) Theme.surface2 else Color.Transparent)
                            .selectable(selected = part == option, role = Role.Tab) { part = option }
                            .testTag("you-${option.lowercase()}"),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(option, style = Theme.label, color = if (part == option) Theme.text else Theme.text2)
                    }
                }
            }
        }
        // The title has the status bar; the halves sit right under it.
        Box(Modifier.weight(1f).consumeWindowInsets(WindowInsets.statusBars)) {
            if (part == "Progress") ProgressScreen(model) else ProfileTab(model, nav)
        }
    }
}
