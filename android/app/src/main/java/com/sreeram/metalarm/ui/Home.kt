// Home: who you are in the game, this week in three numbers, and how you
// stand in your party - its top three and you, with the full leaderboard one
// tap away. One primary: Start workout (or Resume, while one is live). The
// twin of the iOS HomeView and LeaderboardView.

package com.sreeram.metalarm.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.outlined.Groups
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.sreeram.metalarm.api.League
import com.sreeram.metalarm.api.PartyRaid
import com.sreeram.metalarm.api.PartyBoardEntry
import com.sreeram.metalarm.api.PointsSummary
import com.sreeram.metalarm.api.RankTitle
import com.sreeram.metalarm.api.initials
import com.sreeram.metalarm.api.plural
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.theme.Avatar
import com.sreeram.metalarm.theme.ButtonKind
import com.sreeram.metalarm.theme.Chip
import com.sreeram.metalarm.theme.ChipRow
import com.sreeram.metalarm.theme.EmptyState
import com.sreeram.metalarm.theme.ErrorState
import com.sreeram.metalarm.theme.IconButton
import com.sreeram.metalarm.theme.ListRow
import com.sreeram.metalarm.theme.MAButton
import com.sreeram.metalarm.theme.Pill
import com.sreeram.metalarm.theme.ProgressBar
import com.sreeram.metalarm.theme.RankBadge
import com.sreeram.metalarm.theme.RowGroup
import com.sreeram.metalarm.theme.Screen
import com.sreeram.metalarm.theme.SectionBlock
import com.sreeram.metalarm.theme.StatTile
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.theme.card
import kotlinx.coroutines.launch

@Composable
fun HomeTab(model: AppModel, nav: NavHostController, onOpenWorkout: () -> Unit) {
    NavHost(nav, startDestination = "home") {
        composable("home") { HomeScreen(model, onOpenWorkout, onSeeAll = { nav.navigate("leaderboard") }) }
        composable("leaderboard") { LeaderboardScreen(model, onBack = { nav.popBackStack() }) }
    }
}

@Composable
fun HomeScreen(model: AppModel, onOpenWorkout: () -> Unit, onSeeAll: () -> Unit) {
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { model.loadHome() }
    LaunchedEffect(Unit) { model.loadParties() }

    Screen(
        pinned = {
            MAButton(
                if (model.sessionActive) "Resume workout" else "Start workout",
                {
                    scope.launch {
                        if (!model.sessionActive) model.startWorkout()
                        if (model.sessionActive) onOpenWorkout()
                    }
                },
                Modifier.testTag("homeStartWorkoutButton"),
                icon = Icons.Filled.PlayArrow,
            )
        },
    ) {
        Header(model)
        model.points?.let { Week(it) }
        LeaderboardPreview(model, onSeeAll)
        ErrorState(model.errorMessage)
    }
}

@Composable
private fun Header(model: AppModel) {
    val progress = model.me?.progress
    Column(Modifier.padding(top = Theme.Space.s16), verticalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
            RankBadge(progress?.rank ?: "E", size = 48.dp)
            Column {
                Text("Hi, ${model.me?.displayName ?: ""}", style = Theme.title, color = Theme.text, maxLines = 1)
                if (progress != null) {
                    Text("Level ${progress.currentLevel} · ${RankTitle.of(progress.rank)}", style = Theme.caption, color = Theme.text2)
                }
            }
        }
        if (progress != null) {
            ProgressBar(
                progress.xpProgress,
                label = "${progress.xpIntoLevel} / ${progress.xpForNextLevel} XP to level ${progress.currentLevel + 1}",
            )
            progress.nextRankTrial?.let {
                Text("Trial: $it", style = Theme.caption, color = Theme.text2, modifier = Modifier.testTag("nextTrialText"))
            }
        }
    }
}

@Composable
private fun Week(points: PointsSummary) {
    Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
        Row(horizontalArrangement = Arrangement.spacedBy(Theme.Space.s16)) {
            StatTile("${points.streak.weeks}", "Week streak", Modifier.weight(1f))
            StatTile("${points.streak.thisWeekSessions}/${points.streak.target}", "Workouts this week", Modifier.weight(1f))
            StatTile("${points.thisWeekPoints}", "Points this week", Modifier.weight(1f))
        }
        Text(
            if (points.streak.thisWeekDone) "Weekly goal met - your streak is safe."
            else "${plural(points.streak.sessionsToGo, "more workout")} this week keeps your streak.",
            style = Theme.caption, color = Theme.text2,
        )
    }
}

@Composable
private fun LeaderboardPreview(model: AppModel, onSeeAll: () -> Unit) {
    val entries = model.partyBoard?.entries.orEmpty()
    val top = entries.take(3)
    val me = entries.firstOrNull { it.isMe }
    SectionBlock("Leaderboard", action = "See all", onAction = onSeeAll, modifier = Modifier.testTag("homeLeaderboard")) {
        if (entries.isEmpty()) {
            Text("Join or create a party to see how you stack up.", style = Theme.body, color = Theme.text2)
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
                top.forEach { BoardRow(it.position, it.displayName, "${it.points}", it.isMe, rank = it.rank, tag = "homeBoardRow-${it.displayName}") }
                if (me != null && top.none { it.isMe }) {
                    BoardRow(me.position, me.displayName, "${me.points}", true, rank = me.rank, tag = "homeBoardRow-${me.displayName}")
                }
            }
        }
    }
}

/** One line of a board: place, name (rank beside it), the number it is
 *  ranked by. Yours is tinted. */
@Composable
fun BoardRow(
    position: Int, name: String, value: String, isMe: Boolean,
    detail: String = "", rank: String? = null, tag: String = "",
) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = Theme.rowMin)
            .background(if (isMe) Theme.accentSoft else Theme.bg, RoundedCornerShape(Theme.radius))
            .semantics(mergeDescendants = true) {}
            .then(if (tag.isNotEmpty()) Modifier.testTag(tag) else Modifier)
            .padding(horizontal = Theme.Space.s8),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Theme.Space.s12),
    ) {
        Text("$position", style = Theme.label, color = Theme.text2, modifier = Modifier.width(Theme.Space.s24))
        Avatar(initials(name))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Theme.Space.s8)) {
                Text(name + if (isMe) " (you)" else "", style = Theme.body, color = Theme.text, maxLines = 1)
                if (rank != null) RankBadge(rank, size = 24.dp)
            }
            if (detail.isNotEmpty()) Text(detail, style = Theme.caption, color = Theme.text2)
        }
        Text(value, style = Theme.body, color = Theme.text2)
    }
}

/** A detail screen's top bar: back, a title, one optional trailing action. */
@Composable
fun TopBar(title: String, onBack: () -> Unit, trailing: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().heightIn(min = Theme.touch), verticalAlignment = Alignment.CenterVertically) {
        IconButton(Icons.AutoMirrored.Filled.ArrowBack, "Back", onBack, Modifier.testTag("backButton"), tint = Theme.text)
        Text(title, style = Theme.label, color = Theme.text, modifier = Modifier.weight(1f).padding(start = Theme.Space.s4), maxLines = 1)
        trailing?.invoke()
    }
}

/** The leaderboard, opened from Home: the party's weekly board, this week's
 *  league, and the party raid. Parties are how friends compete. */
@Composable
fun LeaderboardScreen(model: AppModel, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var creating by remember { mutableStateOf(false) }
    var joining by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { model.loadParties() }
    LaunchedEffect(Unit) { model.loadLeague() }

    Screen {
        TopBar("Leaderboard", onBack) {
            if (model.parties.isNotEmpty()) {
                androidx.compose.foundation.layout.Box {
                    IconButton(Icons.Filled.Add, "Add a party", { menu = true }, Modifier.testTag("addPartyButton"))
                    DropdownMenu(menu, { menu = false }, containerColor = Theme.surface2) {
                        DropdownMenuItem({ Text("Create a party", style = Theme.body) }, { menu = false; creating = true })
                        DropdownMenuItem({ Text("Join with a code", style = Theme.body) }, { menu = false; joining = true })
                    }
                }
            }
        }
        model.league?.let { LeagueSection(it) }
        if (model.parties.isEmpty()) {
            if (!model.isBusy) {
                Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                    EmptyState(Icons.Outlined.Groups, "Create a party and share its code, or join one. Members are ranked by workout points each week.")
                    MAButton("Create a party", { creating = true }, Modifier.testTag("createPartyButton"))
                    MAButton("Join with an invite code", { joining = true }, Modifier.testTag("joinPartyButton"), kind = ButtonKind.Secondary)
                }
            }
        } else {
            SectionBlock(model.selectedParty?.name ?: "Your party") {
                if (model.parties.size > 1) {
                    ChipRow {
                        model.parties.forEach { party ->
                            Chip(party.name, { scope.launch { model.selectParty(party.id) } }, selected = party.id == model.selectedPartyId)
                        }
                    }
                }
                Text("This week", style = Theme.caption, color = Theme.text2)
                Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
                    model.partyBoard?.entries.orEmpty().forEach { entry: PartyBoardEntry ->
                        BoardRow(
                            entry.position, entry.displayName, "${entry.points}", entry.isMe,
                            detail = plural(entry.workouts, "workout"), rank = entry.rank, tag = "partyRow-${entry.displayName}",
                        )
                    }
                }
            }
            model.partyRaid?.let { RaidSection(it) }
            val party = model.selectedParty
            val code = party?.inviteCode
            if (party != null && code != null) {
                Row(Modifier.card(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Invite code", style = Theme.caption, color = Theme.text2)
                        Text(code, style = Theme.title, color = Theme.text)
                    }
                    MAButton("Share", { shareText(context, "Join my MetalArm party \"${party.name}\" with invite code $code.") },
                        kind = ButtonKind.Ghost, icon = Icons.Filled.Share)
                }
            }
        }
        ErrorState(model.errorMessage)
    }

    if (creating) {
        TextPrompt("Create a party", "Friends join with the invite code you share.", "Party name", "Create",
            onDismiss = { creating = false }) { name -> scope.launch { model.createParty(name) } }
    }
    if (joining) {
        TextPrompt("Join a party", "Enter the code a party member shared with you.", "Invite code", "Join",
            onDismiss = { joining = false }) { code -> scope.launch { model.joinParty(code) } }
    }
}

@Composable
private fun LeagueSection(league: League) {
    SectionBlock("League", modifier = Modifier.testTag("leagueCard")) {
        Text("${league.divisionLabel} · ${league.daysLeft()} days left", style = Theme.caption, color = Theme.text2)
        league.me?.let {
            Text("You're ${it.position} of ${league.entries.size} with ${it.points} points", style = Theme.body, color = Theme.text)
        }
        Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s4)) {
            league.entries.take(5).forEach { BoardRow(it.position, it.displayName, "${it.points}", it.isMe) }
        }
        Text("Top ${league.promoteCutoff} move up. Bottom places move down.", style = Theme.caption, color = Theme.text2)
    }
}

@Composable
private fun RaidSection(raid: PartyRaid) {
    SectionBlock("Party raid", modifier = Modifier.testTag("raidCard")) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(raid.name, style = Theme.body, color = Theme.text, modifier = Modifier.weight(1f))
            if (raid.defeated) Pill("Defeated") else Text(plural(raid.daysLeft(), "day") + " left", style = Theme.caption, color = Theme.text2)
        }
        ProgressBar(
            raid.hpFraction,
            label = "%,d / %,d HP".format(raid.hpRemaining, raid.maxHp) +
                if (raid.healed > 0 && !raid.defeated) " · +%,d healed on idle days".format(raid.healed) else "",
        )
        if (raid.hitters.isEmpty()) {
            Text("No hits yet. Finish a workout to strike first.", style = Theme.body, color = Theme.text2)
        } else {
            RowGroup {
                raid.hitters.take(3).forEach { hitter ->
                    row { ListRow(hitter.displayName + if (hitter.isMe) " (you)" else "", trailing = "%,d dmg".format(hitter.damage)) }
                }
            }
        }
    }
}

/** A one-field dialog: name a party, enter a code. */
@Composable
fun TextPrompt(
    title: String, message: String, placeholder: String, confirm: String,
    onDismiss: () -> Unit, onConfirm: (String) -> Unit,
) {
    var text by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Theme.surface,
        title = { Text(title, style = Theme.title, color = Theme.text) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(Theme.Space.s12)) {
                Text(message, style = Theme.body, color = Theme.text2)
                Field(text, { text = it }, placeholder, "promptField")
            }
        },
        confirmButton = {
            TextButton({ onDismiss(); onConfirm(text) }, Modifier.testTag("promptConfirm")) { Text(confirm, style = Theme.label, color = Theme.accent) }
        },
        dismissButton = { TextButton(onDismiss, Modifier.testTag("promptCancel")) { Text("Cancel", style = Theme.label, color = Theme.text2) } },
    )
}

fun shareText(context: android.content.Context, text: String) {
    val send = android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain").putExtra(android.content.Intent.EXTRA_TEXT, text)
    context.startActivity(android.content.Intent.createChooser(send, null))
}

