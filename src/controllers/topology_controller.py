from src.layers.commonService import file_io
from src.layers.helperService import calculations, converters, json_service, topology_defaults, validators
from src.layers.logService.event_logger import LogCategory, logger


class TopologyController:
    """Bridge between the topology view and the common/helper service layers."""

    # ── calculations ─────────────────────────────────────────────────────────

    def calc_bandwidth(self, packet_size_bytes, period_ns, link_datarate_Mbps: float) -> tuple[float, float]:
        return calculations.calc_bandwidth(packet_size_bytes, period_ns, link_datarate_Mbps)

    def total_bandwidth(self, streams: list, link_datarate_Mbps: float) -> tuple[float, float]:
        return calculations.total_bandwidth(streams, link_datarate_Mbps)

    # ── validation ───────────────────────────────────────────────────────────

    def stream_status(self, streams: list) -> tuple[str, str]:
        return validators.stream_status(streams)

    # ── defaults ─────────────────────────────────────────────────────────────

    def default_edges(self, n_talkers: int, n_listeners: int) -> list:
        return topology_defaults.default_edges(n_talkers, n_listeners)

    def default_workload_rows(self, num_talkers: int) -> list:
        return topology_defaults.default_workload_rows(num_talkers)

    # ── DataFrame conversions ────────────────────────────────────────────────

    def streams_to_df(self, streams: list, link_datarate: float):
        return converters.streams_to_df(streams, link_datarate)

    def df_to_streams(self, df) -> list:
        return converters.df_to_streams(df)

    def edges_to_df(self, edges: list):
        return converters.edges_to_df(edges)

    def df_to_edges(self, df) -> list:
        return converters.df_to_edges(df)

    # ── JSON import ──────────────────────────────────────────────────────────

    def read_json_upload(self, uploaded_file):
        """Raises ValueError if the uploaded file isn't valid JSON."""
        try:
            return file_io.read_json_file(uploaded_file)
        except ValueError as e:
            logger.error(
                LogCategory.FILE, "topology_upload_invalid",
                f"Failed to parse uploaded file '{getattr(uploaded_file, 'name', '?')}' as JSON",
                exc=e,
            )
            raise

    def extract_runs(self, content) -> list:
        return json_service.extract_runs(content)

    def normalize_topology_payload(self, data: dict, allowed_patterns: list) -> dict:
        return json_service.normalize_topology_payload(data, allowed_patterns)

    # ── logging ──────────────────────────────────────────────────────────────

    def log_topology_loaded(self, num_talkers: int, num_switches: int, num_listeners: int) -> None:
        logger.info(
            LogCategory.TOPOLOGY, "topology_loaded",
            f"Topology loaded: {num_talkers} talker(s), {num_switches} switch(es), {num_listeners} listener(s)",
            num_talkers=num_talkers, num_switches=num_switches, num_listeners=num_listeners,
        )

    def log_topology_loaded_from_file(self, run_count: int, selected_index: int) -> None:
        logger.success(
            LogCategory.FILE, "topology_loaded_from_file",
            f"Loaded topology/workload from uploaded file (run {selected_index + 1} of {run_count})",
            run_count=run_count, selected_index=selected_index,
        )

    def log_topology_file_empty(self) -> None:
        logger.warning(
            LogCategory.FILE, "topology_file_empty",
            "Uploaded file contained no topology/workload data",
        )
