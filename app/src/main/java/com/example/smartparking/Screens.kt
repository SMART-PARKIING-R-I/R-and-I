package com.example.smartparking

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

private val Ink = Color(0xFF0F172A)
private val Bg = Color(0xFFF1F5F9)
private val Muted = Color(0xFF64748B)
private val Line = Color(0xFFE2E8F0)

@Composable
fun ParkingApp(vm: ParkingViewModel) {
    MaterialTheme {
        Column(Modifier.fillMaxSize().background(Bg).systemBarsPadding()) {
            TopBar(vm)
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when (val s = vm.screen) {
                    is Screen.Route -> RouteScreen(vm, s.a)
                    is Screen.Thanks -> ThanksScreen(vm, s.number)
                    else -> HomeScreen(vm, s)
                }
            }
        }
    }
}

@Composable
private fun TopBar(vm: ParkingViewModel) {
    val name = vm.status?.name ?: "Parking space A"
    Row(Modifier.fillMaxWidth().background(Color.White).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(RouteBlue), contentAlignment = Alignment.Center) {
            Text("P", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text("BOTSWANA ACCOUNTANCY COLLEGE", color = Muted, fontSize = 11.sp, letterSpacing = 0.8.sp, fontWeight = FontWeight.SemiBold)
            Text(name, color = Ink, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
        }
        Row(Modifier.clip(RoundedCornerShape(50)).background(if (vm.online) Color(0xFFDCFCE7) else Color(0xFFFEE2E2))
            .padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Dot(if (vm.online) FreeGreen else BusyRed, 8.dp)
            Spacer(Modifier.width(6.dp))
            Text(if (vm.online) "Live" else "Offline", fontSize = 12.sp, fontWeight = FontWeight.Bold,
                color = if (vm.online) Color(0xFF166534) else Color(0xFF991B1B))
        }
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(Line))
}

@Composable
private fun Dot(color: Color, size: Dp = 10.dp) = Box(Modifier.size(size).clip(CircleShape).background(color))

@Composable
private fun LegendItem(color: Color, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Dot(color); Spacer(Modifier.width(6.dp))
        Text(text, color = Ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun CardBox(modifier: Modifier, content: @Composable () -> Unit) {
    Card(modifier, shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) { content() }
}

@Composable
private fun PrimaryButton(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Button(onClick, modifier.height(58.dp), shape = RoundedCornerShape(16.dp),
        colors = ButtonDefaults.buttonColors(containerColor = RouteBlue, contentColor = Color.White)) {
        Text(text, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold, textAlign = TextAlign.Center)
    }
}

/** Welcome / Finding / Full: live lot overview + the action card. */
@Composable
private fun HomeScreen(vm: ParkingViewModel, s: Screen) {
    val st = vm.status
    val map = vm.lotMap
    val free = st?.free ?: 0
    val total = st?.total ?: 0
    BoxWithConstraints(Modifier.fillMaxSize().padding(16.dp)) {
        val wide = maxWidth > maxHeight

        val mapCard: @Composable (Modifier) -> Unit = { m ->
            CardBox(m) {
                Column(Modifier.padding(14.dp)) {
                    Row(Modifier.fillMaxWidth().padding(bottom = 10.dp), horizontalArrangement = Arrangement.spacedBy(18.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text("Live lot view", color = Ink, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold, modifier = Modifier.weight(1f))
                        LegendItem(FreeGreen, "Free $free")
                        LegendItem(BusyRed, "Occupied ${total - free}")
                    }
                    Box(Modifier.fillMaxWidth().then(if (map != null) Modifier.aspectRatio(map.width / map.height.toFloat()) else Modifier.height(200.dp))
                        .clip(RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                        if (map != null && st != null) LotMapView(map, st.freeIds, null, false)
                        else CircularProgressIndicator(color = RouteBlue)
                        if (s is Screen.Finding) Box(Modifier.fillMaxSize().background(Ink.copy(alpha = 0.35f)))
                    }
                }
            }
        }

        val actionCard: @Composable (Modifier) -> Unit = { m ->
            CardBox(m) {
                Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center) {
                    when (s) {
                        is Screen.Finding -> {
                            CircularProgressIndicator(Modifier.size(64.dp), color = RouteBlue, trackColor = Line, strokeWidth = 7.dp)
                            Spacer(Modifier.height(24.dp))
                            Text("Finding your space…", color = Ink, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, textAlign = TextAlign.Center)
                            Text("Checking the live camera view", color = Muted, fontSize = 16.sp, modifier = Modifier.padding(top = 8.dp))
                        }
                        is Screen.Full -> {
                            Box(Modifier.clip(RoundedCornerShape(50)).background(Color(0xFFFEE2E2)).padding(horizontal = 16.dp, vertical = 8.dp)) {
                                Text("0 of $total free", color = Color(0xFF991B1B), fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            }
                            Spacer(Modifier.height(18.dp))
                            Text("The lot is full right now", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, textAlign = TextAlign.Center, lineHeight = 32.sp)
                            Text("Please wait here. This screen updates as soon as a space opens.", color = Muted, fontSize = 16.sp,
                                textAlign = TextAlign.Center, modifier = Modifier.padding(top = 10.dp, bottom = 24.dp))
                            OutlinedButton({ vm.checkAgain() }, Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(16.dp),
                                border = BorderStroke(2.dp, RouteBlue),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = RouteBlue)) {
                                Text("Check again", fontSize = 17.sp, fontWeight = FontWeight.ExtraBold)
                            }
                        }
                        else -> {
                            Text("PARKING GUIDANCE", color = RouteBlue, fontSize = 12.sp, letterSpacing = 1.2.sp, fontWeight = FontWeight.ExtraBold)
                            Spacer(Modifier.height(8.dp))
                            Text("Need a parking space?", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, textAlign = TextAlign.Center, lineHeight = 32.sp)
                            Row(Modifier.padding(vertical = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text(if (st == null) "–" else "$free", color = FreeGreen, fontSize = 64.sp, fontWeight = FontWeight.ExtraBold)
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text("spaces free", color = Ink, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                                    Text(if (vm.online) "of $total · live from cameras" else "Cannot reach server", color = Muted, fontSize = 13.sp)
                                }
                            }
                            PrimaryButton("Find me a space", Modifier.fillMaxWidth()) { vm.find() }
                            Text("We pick the nearest free bay and show you the way.", color = Muted, fontSize = 13.sp,
                                textAlign = TextAlign.Center, modifier = Modifier.padding(top = 12.dp))
                        }
                    }
                }
            }
        }

        if (wide) {
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                mapCard(Modifier.weight(0.62f))
                actionCard(Modifier.weight(0.38f).fillMaxHeight())
            }
        } else {
            Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                mapCard(Modifier.fillMaxWidth())
                actionCard(Modifier.weight(1f).fillMaxWidth())
            }
        }
    }
}

@Composable
private fun RouteScreen(vm: ParkingViewModel, a: Assignment) {
    var zoom by remember { mutableStateOf(true) }
    val map = vm.lotMap
    val st = vm.status
    val name = st?.name ?: "Parking space A"
    BoxWithConstraints(Modifier.fillMaxSize().padding(16.dp)) {
        val wide = maxWidth > maxHeight

        val mapCard: @Composable (Modifier) -> Unit = { m ->
            CardBox(m) {
                Box(Modifier.fillMaxSize().clip(RoundedCornerShape(20.dp))) {
                    if (map != null && st != null) LotMapView(map, st.freeIds, a, zoom)
                    Box(Modifier.align(Alignment.TopStart).padding(12.dp).clip(RoundedCornerShape(50))
                        .background(Ink.copy(alpha = 0.88f)).padding(horizontal = 14.dp, vertical = 8.dp)) {
                        Text("Follow the blue route", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    }
                    Row(Modifier.align(Alignment.BottomStart).padding(12.dp).clip(RoundedCornerShape(50))
                        .background(Color.White.copy(alpha = 0.94f)).padding(horizontal = 12.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        LegendItem(FreeGreen, "Free"); LegendItem(BusyRed, "Occupied")
                    }
                    Box(Modifier.align(Alignment.BottomEnd).padding(12.dp).clip(RoundedCornerShape(50))
                        .background(Color.White.copy(alpha = 0.94f)).clickable { zoom = !zoom }
                        .padding(horizontal = 14.dp, vertical = 8.dp)) {
                        Text(if (zoom) "Whole lot" else "My route", color = RouteBlue, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        val infoCard: @Composable (Modifier) -> Unit = { m ->
            CardBox(m) {
                Column(Modifier.padding(20.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.clip(RoundedCornerShape(16.dp)).background(FreeGreen).padding(horizontal = 18.dp, vertical = 8.dp)) {
                            Text("${a.number}", color = Color.White, fontSize = if (wide) 56.sp else 44.sp, fontWeight = FontWeight.ExtraBold)
                        }
                        Spacer(Modifier.width(16.dp))
                        Column {
                            Text("YOUR SPACE", color = FreeGreen, fontSize = 12.sp, letterSpacing = 1.2.sp, fontWeight = FontWeight.ExtraBold)
                            Text(name, color = Ink, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold)
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                    a.steps.forEachIndexed { i, t ->
                        Row(Modifier.padding(vertical = 5.dp), verticalAlignment = Alignment.Top) {
                            Box(Modifier.size(26.dp).clip(CircleShape).background(Ink), contentAlignment = Alignment.Center) {
                                Text("${i + 1}", color = Color.White, fontWeight = FontWeight.ExtraBold, fontSize = 13.sp)
                            }
                            Spacer(Modifier.width(12.dp))
                            Text(t, color = Ink, fontSize = 15.sp, lineHeight = 20.sp, modifier = Modifier.padding(top = 2.dp))
                        }
                    }
                    if (wide) Spacer(Modifier.weight(1f)) else Spacer(Modifier.height(14.dp))
                    PrimaryButton("Confirm, I know where to go", Modifier.fillMaxWidth()) { vm.confirm(a) }
                }
            }
        }

        if (wide) {
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                mapCard(Modifier.weight(0.62f).fillMaxHeight())
                infoCard(Modifier.weight(0.38f).fillMaxHeight())
            }
        } else {
            Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                mapCard(Modifier.weight(1f).fillMaxWidth())
                infoCard(Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun ThanksScreen(vm: ParkingViewModel, number: Int) {
    val name = vm.status?.name ?: "Parking space A"
    var left by remember { mutableStateOf(5) }
    LaunchedEffect(Unit) {
        while (left > 0) { delay(1000); left-- }
        vm.reset()
    }
    Box(Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.Center) {
        CardBox(Modifier.fillMaxWidth().then(Modifier.padding(horizontal = 0.dp))) {
            Column(Modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.size(84.dp).clip(CircleShape).background(FreeGreen), contentAlignment = Alignment.Center) {
                    Text("✓", color = Color.White, fontSize = 46.sp, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(22.dp))
                Text("Thank you. Drive safely.", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, textAlign = TextAlign.Center)
                Spacer(Modifier.height(16.dp))
                Box(Modifier.clip(RoundedCornerShape(16.dp)).background(Color(0xFFDCFCE7)).padding(horizontal = 20.dp, vertical = 10.dp)) {
                    Text("Space $number · $name", color = Color(0xFF166534), fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
                }
                Text("This screen restarts in $left seconds for the next driver.", color = Muted, fontSize = 14.sp,
                    textAlign = TextAlign.Center, modifier = Modifier.padding(top = 18.dp))
            }
        }
    }
}
