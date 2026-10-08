package androidx.compose.ui.test

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull

/** Nodes whose test tag starts with `prefix` - for lists from a live server. */
fun hasTestTagPrefix(prefix: String): SemanticsMatcher =
    SemanticsMatcher("TestTag starts with '$prefix'") { node ->
        node.config.getOrNull(SemanticsProperties.TestTag)?.startsWith(prefix) == true
    }
