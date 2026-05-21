package com.saki.bytedance.ragshopping

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                ShoppingAgentApp()
            }
        }
    }
}

@Composable
fun ShoppingAgentApp(viewModel: ChatViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    Surface(color = Color(0xFFF3FBF6), modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
            Header()
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.messages) { message ->
                    MessageBubble(message = message)
                }
            }
            InputBar(
                value = state.input,
                isLoading = state.isLoading,
                onValueChange = viewModel::updateInput,
                onSend = viewModel::send,
            )
        }
    }
}

@Composable
private fun Header() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .padding(horizontal = 20.dp, vertical = 16.dp),
    ) {
        Text("RAG 美妆导购", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
        Text("肤质、预算、场景和排除条件都可以直接说", color = Color(0xFF5D6B63))
    }
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    val alignment = if (message.role == Role.User) Alignment.End else Alignment.Start
    val background = when (message.role) {
        Role.User -> Color(0xFF0BAE5C)
        Role.Assistant -> Color.White
        Role.Status -> Color(0xFFE4F6EA)
        Role.Error -> Color(0xFFFFECE8)
    }
    val textColor = if (message.role == Role.User) Color.White else Color(0xFF1F2937)

    Column(horizontalAlignment = alignment, modifier = Modifier.fillMaxWidth()) {
        Card(
            colors = CardDefaults.cardColors(containerColor = background),
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth(if (message.role == Role.User) 0.86f else 1f),
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (message.content.isNotBlank()) {
                    Text(message.content, color = textColor)
                }
                message.products.forEach { ProductCardView(it) }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProductCardView(product: ProductCard) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF8FFFA)),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(
                    modifier = Modifier
                        .size(52.dp)
                        .background(Color(0xFFDFF5E8), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(product.brand.take(1), fontWeight = FontWeight.Bold, color = Color(0xFF087A42))
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text(product.brand, color = Color(0xFF087A42), fontWeight = FontWeight.Bold)
                    Text(product.title, maxLines = 2, style = MaterialTheme.typography.bodySmall)
                }
                Text("¥${product.price.toInt()}", color = Color(0xFFE87800), fontWeight = FontWeight.Bold)
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                product.tags.forEach { tag ->
                    Text(
                        text = tag,
                        modifier = Modifier
                            .background(Color(0xFFFFF1D8), RoundedCornerShape(999.dp))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                        color = Color(0xFF9A4B00),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
            Text(product.reason, color = Color(0xFF53635A), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun InputBar(
    value: String,
    isLoading: Boolean,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.weight(1f),
            minLines = 1,
            maxLines = 3,
            placeholder = { Text("例如：我是油皮，想要200元以内通勤防晒") },
        )
        Button(
            onClick = onSend,
            enabled = !isLoading && value.isNotBlank(),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0BAE5C)),
        ) {
            Text(if (isLoading) "中" else "发")
        }
    }
    Spacer(modifier = Modifier.height(4.dp))
}
