from .isolation_forest import IFDetector


class DomainIsolationForest:
    """
    One Isolation Forest per behavioral domain.

    Purpose:
        - Logon anomaly detection
        - File anomaly detection
        - Device anomaly detection
        - HTTP anomaly detection

    Returns domain-specific anomaly scores which are later
    fused into a higher-level risk score.
    """

    def __init__(
        self,
        contamination=0.05,
        random_state=42
    ):

        self.logon_model = IFDetector(
            contamination=contamination,
            random_state=random_state
        )

        self.file_model = IFDetector(
            contamination=contamination,
            random_state=random_state
        )

        self.device_model = IFDetector(
            contamination=contamination,
            random_state=random_state
        )

        self.http_model = IFDetector(
            contamination=contamination,
            random_state=random_state
        )

    def fit(
        self,
        logon_X,
        file_X,
        device_X,
        http_X
    ):
        """
        Train all domain-specific Isolation Forests.

        Parameters
        ----------
        logon_X : np.ndarray
        file_X : np.ndarray
        device_X : np.ndarray
        http_X : np.ndarray
        """

        self.logon_model.fit(logon_X)
        self.file_model.fit(file_X)
        self.device_model.fit(device_X)
        self.http_model.fit(http_X)

    def score(
        self,
        logon_X,
        file_X,
        device_X,
        http_X
    ):
        """
        Returns anomaly scores.

        Higher score = more anomalous.
        """

        return {
            "logon": self.logon_model.score(logon_X),
            "file": self.file_model.score(file_X),
            "device": self.device_model.score(device_X),
            "http": self.http_model.score(http_X)
        }

    def predict(
        self,
        logon_X,
        file_X,
        device_X,
        http_X
    ):
        """
        Returns Isolation Forest predictions.

        sklearn convention:
            1  = normal
           -1 = anomaly
        """

        return {
            "logon": self.logon_model.predict(logon_X),
            "file": self.file_model.predict(file_X),
            "device": self.device_model.predict(device_X),
            "http": self.http_model.predict(http_X)
        }