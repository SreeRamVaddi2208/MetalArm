// Profile - the twin of iOS ProfileView: who you are, your character, rank
// trials and badges, then settings in three groups: Training, App, Account.

package com.sreeram.metalarm.ui

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.EmojiEvents
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.FitnessCenter
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material.icons.outlined.LocalFireDepartment
import androidx.compose.material.icons.outlined.MobileOff
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.PanTool
import androidx.compose.material.icons.outlined.Route
import androidx.compose.material.icons.outlined.Scale
import androidx.compose.material.icons.outlined.WorkspacePremium
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.sreeram.metalarm.BuildConfig
import com.sreeram.metalarm.api.Badge
import com.sreeram.metalarm.api.CharacterSheet
import com.sreeram.metalarm.api.LifetimeStats
import com.sreeram.metalarm.api.Profile
import com.sreeram.metalarm.api.RankTitle
import com.sreeram.metalarm.api.RankTrial
import com.sreeram.metalarm.api.WeightUnit
import com.sreeram.metalarm.api.initials
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.Avatar
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.ProgressBar
import com.sreeram.metalarm.theme.RankBadge
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.ScreenTitle
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.Segmented
import com.sreeram.metalarm.theme.StatTile
import com.sreeram.metalarm.theme.Theme
import kotlinx.coroutines.launch

@Composable
fun ProfileTab(model: AppModel, nav: NavHostController) {
    NavHost(nav, startDestination = "profile") {
        composable("profile") { ProfileScreen(model, onChoosePath = { nav.navigate("path") }) }
        composable("path") {
            Column {
                Box(Modifier.padding(horizontal = Theme.gutter).padding(top = Theme.Space.s8)) { TopBar("Training path", { nav.popBackStack() }) }
                TrainingPathScreen(model, isOnboarding = false) { nav.popBackStack() }
            }
        }
    }
}

@Composable
fun ProfileScreen(model: AppModel, onChoosePath: () -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var deleting by remember { mutableStateOf(false) }
    var confirmingEverywhere by remember { mutableStateOf(false) }
    val importer = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            val csv = readText(context, uri)
            if (csv == null) model.errorMessage = "Couldn't read that file" else scope.launch { model.importWorkouts(csv) }
        }
    }
    LaunchedEffect(Unit) { model.loadProfile() }

    Screen {
        ScreenTitle("Profile")
        model.profile?.let { profile ->
            Header(profile)
            Stats(profile.stats)
            model.characterSheet?.let { Character(it, onChoosePath) }
            if (model.rankTrials.isNotEmpty()) Trials(model.rankTrials, model.weightUnit)
            Badges(profile)
        }
        SectionBlock("Training") {
            RowGroup {
                row {
                    Row(Modifier.heightIn(min = Theme.rowMin), verticalAlignment = Alignment.CenterVertically) {
                        SettingIcon(Icons.Outlined.Scale)
                        Text("Weight unit", style = Theme.body, color = Theme.text, modifier = Modifier.weight(1f).padding(start = Theme.Space.s12))
                        Segmented(
                            WeightUnit.entries.map { it.raw }, model.weightUnit.raw,
                            { raw -> scope.launch { model.setWeightUnit(WeightUnit.of(raw)) } },
                            Modifier.width(120.dp).testTag("weightUnitPicker"),
                        )
                    }
                }
                row {
                    SettingRow("Import from Strong or Hevy", Icons.Outlined.Download, "importWorkoutsButton") {
                        importer.launch(arrayOf("text/csv", "text/comma-separated-values", "text/plain"))
                    }
                }
            }
        }
        SectionBlock("App") {
            RowGroup {
                row {
                    Column {
                        ToggleRow("Save to Health Connect", Icons.Outlined.FavoriteBorder, model.healthSettings.enabled, "healthSyncToggle") {
                            scope.launch { model.setHealthSync(it) }
                        }
                        if (model.healthStatus.isNotEmpty()) {
                            Text(model.healthStatus, style = Theme.caption, color = Theme.text2,
                                modifier = Modifier.padding(bottom = Theme.Space.s8).testTag("healthStatusText"))
                        }
                    }
                }
                row {
                    ToggleRow("Rest timer alerts", Icons.Outlined.NotificationsNone, model.notificationSettings.restAlerts, "restAlertsToggle") {
                        scope.launch { model.setRestAlerts(it) }
                    }
                }
                row {
                    ToggleRow("Streak reminders", Icons.Outlined.LocalFireDepartment, model.notificationSettings.streakReminders, "streakRemindersToggle") {
                        scope.launch { model.setStreakReminders(it) }
                    }
                }
            }
        }
        SectionBlock("Account") {
            RowGroup {
                row { SettingRow("Privacy policy", Icons.Outlined.PanTool, "privacyLink") { openLink(context, BuildConfig.WEB_BASE_URL + "/privacy") } }
                row { SettingRow("Support", Icons.Outlined.HelpOutline, "supportLink") { openLink(context, BuildConfig.WEB_BASE_URL + "/support") } }
                row { SettingRow("Sign out", Icons.AutoMirrored.Outlined.Logout, "signOutButton") { scope.launch { model.signOut() } } }
                row { SettingRow("Sign out of all devices", Icons.Outlined.MobileOff, "signOutEverywhereButton") { confirmingEverywhere = true } }
                row { SettingRow("Delete account", Icons.Outlined.DeleteOutline, "deleteAccountButton", destructive = true) { deleting = true } }
            }
        }
        ErrorState(model.errorMessage)
    }

    if (model.importSummary.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { model.importSummary = "" },
            containerColor = Theme.surface,
            title = { Text("Import finished", style = Theme.title, color = Theme.text) },
            text = { Text(model.importSummary, style = Theme.body, color = Theme.text2) },
            confirmButton = { TextButton({ model.importSummary = "" }) { Text("OK", style = Theme.label, color = Theme.accent) } },
        )
    }
    if (confirmingEverywhere) {
        AlertDialog(
            onDismissRequest = { confirmingEverywhere = false },
            containerColor = Theme.surface,
            title = { Text("Sign out of every device?", style = Theme.title, color = Theme.text) },
            text = { Text("You'll need to sign in again on this and every other device.", style = Theme.body, color = Theme.text2) },
            confirmButton = {
                TextButton({ confirmingEverywhere = false; scope.launch { model.signOutEverywhere() } }, Modifier.testTag("confirmSignOutEverywhere")) {
                    Text("Sign out everywhere", style = Theme.label, color = Theme.danger)
                }
            },
            dismissButton = { TextButton({ confirmingEverywhere = false }) { Text("Cancel", style = Theme.label, color = Theme.text2) } },
        )
    }
    if (deleting) DeleteAccountSheet(model) { deleting = false }
}

private fun readText(context: Context, uri: Uri): String? =
    runCatching { context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } }.getOrNull()

@Composable
private fun Header(profile: Profile) {
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(initials(profile.user.displayName), size = 72.dp)
            Spacer(Modifier.weight(1f))
            RankBadge(profile.progress.rank, size = 72.dp)
        }
        Column {
            Text(profile.user.displayName, style = Theme.titleLG, color = Theme.text)
            Text("${RankTitle.of(profile.progress.rank)} · Level ${profile.progress.currentLevel}", style = Theme.body, color = Theme.text2)
        }
        ProgressBar(profile.progress.xpProgress, label = "${profile.progress.xpIntoLevel} / ${profile.progress.xpForNextLevel} XP to the next level")
    }
}

@Composable
private fun Stats(stats: LifetimeStats) {
    Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
        StatTile("${stats.workoutsCompleted}", "Workouts", Modifier.weight(1f))
        StatTile("${stats.workoutPrs}", "Records", Modifier.weight(1f))
        StatTile("${stats.longestWorkoutStreak}", "Best streak", Modifier.weight(1f), unit = "wk")
    }
}

/** Three stats from real training, plus the path that highlights them. */
@Composable
private fun Character(sheet: CharacterSheet, onChoosePath: () -> Unit) {
    SectionBlock("Character", modifier = Modifier.testTag("characterCard")) {
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
            sheet.stats.forEach { stat ->
                Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
                    Row {
                        Text(stat.label, style = Theme.body, color = if (stat.highlighted) Theme.text else Theme.text2, modifier = Modifier.weight(1f))
                        Text("${stat.value}", style = Theme.body, color = Theme.text)
                    }
                    ProgressBar(stat.fraction, label = stat.detail)
                }
            }
        }
        ListRow(
            "Training path", Modifier.testTag("trainingPathButton"),
            subtitle = sheet.classLabel.ifEmpty { "Not chosen yet" }, chevron = true, onClick = onChoosePath,
        ) { SettingIcon(Icons.Outlined.Route) }
        Text(
            "Your path highlights the stats you care about and decides what MetalArm suggests. It never changes a score.",
            style = Theme.caption, color = Theme.text2,
        )
    }
}

@Composable
private fun Trials(trials: List<RankTrial>, unit: WeightUnit) {
    SectionBlock("Rank trials", modifier = Modifier.testTag("rankTrialsCard")) {
        Text("${RankTitle.list(listOf("B", "A", "S"))} also need a lift at a multiple of your bodyweight.", style = Theme.caption, color = Theme.text2)
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
            trials.forEach { trial ->
                Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                        RankBadge(trial.rank, size = 24.dp)
                        Text(trial.description, style = Theme.body, color = Theme.text, modifier = Modifier.weight(1f))
                        if (trial.passed) Icon(Icons.Filled.Check, contentDescription = "Passed", tint = Theme.accent)
                    }
                    ProgressBar(trial.fraction, label = trialProgress(trial, unit))
                }
            }
        }
    }
}

private fun trialProgress(trial: RankTrial, unit: WeightUnit): String {
    val target = trial.targetKg ?: return "Log your bodyweight to set a target"
    val best = trial.bestKg?.let(unit::format)
    if (trial.passed) return "Passed · best ${best ?: ""}"
    return "Best ${best ?: "none yet"} of ${unit.format(target)}"
}

@Composable
private fun Badges(profile: Profile) {
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Badges", style = Theme.title, color = Theme.text, modifier = Modifier.weight(1f))
            Text("${profile.badgesEarned} of ${profile.badgesTotal}", style = Theme.caption, color = Theme.text2)
        }
        profile.badges.chunked(4).forEach { line ->
            Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                line.forEach { BadgeTile(it, Modifier.weight(1f)) }
                repeat(4 - line.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun BadgeTile(badge: Badge, modifier: Modifier) {
    Column(
        modifier.semantics(mergeDescendants = true) {
            contentDescription = "${badge.name}, ${if (badge.earned) "earned" else "${badge.percent} percent"}. ${badge.description}"
        },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(Theme.Space.s4),
    ) {
        Box(
            Modifier.fillMaxWidth().aspectRatio(1f)
                .background(if (badge.earned) Theme.accentSoft else Theme.surface, RoundedCornerShape(Theme.radius)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(badgeIcon(badge.icon), contentDescription = null, tint = if (badge.earned) Theme.accent else Theme.text3)
        }
        Text(badge.name, style = Theme.caption, color = Theme.text2, textAlign = TextAlign.Center, maxLines = 2)
        if (!badge.earned) Text("${badge.percent}%", style = Theme.caption, color = Theme.text3)
    }
}

/** The server sends an icon name; map the ones it uses, else a rosette. */
private fun badgeIcon(name: String): ImageVector = when (name) {
    "dumbbell" -> Icons.Outlined.FitnessCenter
    "trophy" -> Icons.Outlined.EmojiEvents
    "flame" -> Icons.Outlined.LocalFireDepartment
    "calendar" -> Icons.Outlined.CalendarMonth
    else -> Icons.Outlined.WorkspacePremium
}

@Composable
private fun SettingIcon(icon: ImageVector, tint: Color = Theme.text2) =
    Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.width(Theme.Space.s24))

@Composable
private fun SettingRow(title: String, icon: ImageVector, tag: String, destructive: Boolean = false, onClick: () -> Unit) {
    ListRow(
        title, Modifier.testTag(tag), chevron = true, titleColor = if (destructive) Theme.danger else Theme.text, onClick = onClick,
    ) { SettingIcon(icon, if (destructive) Theme.danger else Theme.text2) }
}

/** No chevron beside a switch: a chevron says "opens something". */
@Composable
private fun ToggleRow(title: String, icon: ImageVector, on: Boolean, tag: String, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = Theme.rowMin), verticalAlignment = Alignment.CenterVertically) {
        SettingIcon(icon)
        Text(title, style = Theme.body, color = Theme.text, modifier = Modifier.weight(1f).padding(start = Theme.Space.s12))
        Switch(
            on, onChange, Modifier.testTag(tag),
            colors = SwitchDefaults.colors(
                checkedThumbColor = Theme.text, checkedTrackColor = Theme.accent,
                uncheckedThumbColor = Theme.text2, uncheckedTrackColor = Theme.surface2, uncheckedBorderColor = Theme.border,
            ),
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DeleteAccountSheet(model: AppModel, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var password by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { model.errorMessage = "" }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = Theme.bg,
        shape = RoundedCornerShape(topStart = Theme.radiusSheet, topEnd = Theme.radiusSheet),
    ) {
        Column(
            Modifier.padding(horizontal = Theme.gutter).padding(bottom = Theme.Space.s32).testTag("deleteAccountSheet"),
            verticalArrangement = Arrangement.spacedBy(Theme.Space.s16),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Delete account", style = Theme.title, color = Theme.text, modifier = Modifier.weight(1f))
                MAButton("Cancel", onDismiss, Modifier.testTag("cancelDeleteButton"), kind = ButtonKind.Ghost)
            }
            Text(
                "This permanently deletes your account and everything you've logged: workouts, records, points, quests and rewards. " +
                    "A party you own passes to its longest-standing member. This can't be undone.",
                style = Theme.body, color = Theme.text2,
            )
            Field(password, { password = it }, "Confirm your password", "deletePasswordField", secure = true)
            ErrorState(model.errorMessage)
            MAButton(
                "Delete my account",
                { scope.launch { if (model.deleteAccount(password)) onDismiss() } },
                Modifier.testTag("confirmDeleteButton"),
                kind = ButtonKind.Danger, enabled = password.isNotEmpty() && !model.isBusy,
            )
        }
    }
}
