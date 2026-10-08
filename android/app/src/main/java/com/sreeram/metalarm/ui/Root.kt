// The app's frame - the twin of the iOS RootView. Onboarding, then sign-in,
// then the training-path question (asked once), then five tabs: Home, Train,
// Library, Progress, Profile. Each tab keeps its own back stack, so a list
// pushes its detail and the system back gesture works per tab. The workout
// summary covers everything when a workout finishes.

package com.sreeram.metalarm.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.LibraryBooks
import androidx.compose.material.icons.automirrored.outlined.ShowChart
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.FitnessCenter
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
    Train("Train", Icons.Outlined.FitnessCenter),
    Library("Library", Icons.AutoMirrored.Outlined.LibraryBooks),
    Progress("Progress", Icons.AutoMirrored.Outlined.ShowChart),
    Profile("Profile", Icons.Outlined.AccountCircle),
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

    Box(Modifier.fillMaxSize()) {
        Scaffold(
            containerColor = Theme.bg,
            contentWindowInsets = WindowInsets(0),
            bottomBar = {
                NavigationBar(containerColor = Theme.surface, tonalElevation = 0.dp) {
                    AppTab.entries.forEach { tab ->
                        NavigationBarItem(
                            selected = tab == selected,
                            onClick = {
                                if (tab == selected) {
                                    // A second tap returns the tab to its root.
                                    controllers.getValue(tab).popBackStack(controllers.getValue(tab).graph.startDestinationId, false)
                                }
                                selected = tab
                            },
                            icon = { Icon(tab.icon, contentDescription = null) },
                            label = { Text(tab.label, style = Theme.caption) },
                            modifier = Modifier.testTag("tab-${tab.name.lowercase()}"),
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = Theme.accent, selectedTextColor = Theme.accent,
                                indicatorColor = Theme.accentSoft, unselectedIconColor = Theme.text2,
                                unselectedTextColor = Theme.text2,
                            ),
                        )
                    }
                }
            },
        ) { padding ->
            Column(Modifier.fillMaxSize().padding(padding)) {
                saveable.SaveableStateProvider(selected.name) {
                    val nav = controllers.getValue(selected)
                    when (selected) {
                        AppTab.Home -> HomeTab(model, nav, onOpenWorkout = { selected = AppTab.Train })
                        AppTab.Train -> WorkoutScreen(model, onOpenLibrary = { selected = AppTab.Library })
                        AppTab.Library -> LibraryTab(model, nav, onStarted = { selected = AppTab.Train })
                        AppTab.Progress -> ProgressScreen(model)
                        AppTab.Profile -> ProfileTab(model, nav)
                    }
                }
            }
        }

        val result = model.finishResult
        if (model.showingSummary && result != null) {
            SummaryScreen(result, model.weightUnit, model.shareInviteCode) { model.showingSummary = false }
        }
    }
}
