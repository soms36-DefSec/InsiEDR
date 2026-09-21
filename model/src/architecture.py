import torch
import torch.nn as nn
import numpy as np

# Random LSTM feature extractor
class RandomLSTM(nn.Module):

    def __init__(self, input_size, hidden_size):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            batch_first=True
        )

        # Freeze all LSTM parameters
        for param in self.lstm.parameters():
            param.requires_grad = False

        self.eval()

    def forward(self, x):
        batch_size = x.shape[0]
        chunk_size = 8192

        if batch_size <= chunk_size:
            with torch.no_grad():
                # output, (h_n, c_n)
                _, (h_n, _) = self.lstm(x)
            hidden_state = h_n[-1]
            return hidden_state

        h_ns = []
        with torch.no_grad():
            for start_idx in range(0, batch_size, chunk_size):
                end_idx = min(start_idx + chunk_size, batch_size)
                x_chunk = x[start_idx:end_idx]
                _, (h_n_chunk, _) = self.lstm(x_chunk)
                h_ns.append(h_n_chunk[-1])
        
        hidden_state = torch.cat(h_ns, dim=0)
        return hidden_state



def flatten_window(X):
    """
    Flatten input time window.

    Input:
        torch tensor
        (batch_size, window_size, features)

    Output:
        numpy array
        (batch_size, window_size * features)
    """

    batch_size = X.shape[0]

    xflat = X.reshape(batch_size, -1)

    # convert to numpy for ridge regression
    return xflat.detach().cpu().numpy()


def build_layer_input(previous_hidden, xtensor):
    """
    Construct input for deeper RedRVFL layers.

    Layer l receives:
        [h_(l-1) , X]

    previous_hidden:
        torch tensor
        (batch_size, hidden_size)

    xtensor:
        torch tensor
        (batch_size, window_size, features)

    returns:
        torch tensor
        (batch_size, window_size, features + hidden_size)
    """

    window_size = xtensor.shape[1]

    # expand hidden representation across time dimension
    hidden_expanded = previous_hidden.unsqueeze(1).repeat(1, window_size, 1)

    # concatenate along feature dimension
    layer_input = torch.cat([xtensor, hidden_expanded], dim=2)

    return layer_input


def build_feature_matrix(xtensor, hidden_tensor):
    """
    Build RVFL feature matrix.

    D = [hidden_features , flattened_input]

    Input:
        xtensor:
            (batch_size, window_size, features)

        hidden_tensor:
            (batch_size, hidden_size)

    Output:
        D:
            numpy array
            (batch_size, hidden_size + window_size * features)
    """

    # flatten original input
    xflat = flatten_window(xtensor)

    # convert hidden features to numpy
    hidden_np = hidden_tensor.detach().cpu().numpy()

    # concatenate features
    D = np.concatenate([hidden_np, xflat], axis=1)

    return D