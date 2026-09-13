"""
Data Export
CSV/JSON output, HDF5 for large datasets,
statistics computation, and result visualization.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np
import json
from pathlib import Path
from datetime import datetime


@dataclass
class ExportConfig:
    """Configuration for data export."""
    format: str = "csv"  # csv, json, hdf5
    include_metadata: bool = True
    include_statistics: bool = True
    compression: str = "none"  # none, gzip, lz4
    chunk_size: int = 1000  # For large exports


class DataExporter:
    """
    Exports simulation data in various formats.
    Supports CSV, JSON, HDF5, and statistical analysis.
    """

    def __init__(self, config: ExportConfig):
        """
        Initialize exporter.

        Args:
            config: ExportConfig object
        """
        self.config = config

    def export_csv(
        self,
        data: Dict[str, np.ndarray],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Export data to CSV format.

        Args:
            data: Dictionary of arrays to export
            output_path: Path to save CSV
            metadata: Optional metadata

        Returns:
            True if successful
        """
        try:
            # Prepare data for CSV
            time_array = data.get("time", np.arange(len(list(data.values())[0])))

            # Build rows
            rows = []
            if self.config.include_metadata and metadata:
                rows.append(["# Metadata"])
                for key, value in metadata.items():
                    rows.append([f"# {key}: {value}"])
                rows.append(["#"])

            # Add header
            headers = ["time"]
            headers.extend(data.keys())
            if "time" in data:
                headers.remove("time")
            rows.append(headers)

            # Add data rows
            n_rows = len(time_array)
            for i in range(n_rows):
                row = [time_array[i]]
                for key, array in data.items():
                    if key != "time":
                        if array.ndim == 1:
                            row.append(array[i])
                        else:
                            # Flatten multidimensional data
                            row.extend(array[i].flatten())
                rows.append(row)

            # Write to CSV
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                for row in rows:
                    f.write(",".join(str(x) for x in row) + "\n")

            return True

        except Exception as e:
            print(f"CSV export error: {e}")
            return False

    def export_json(
        self,
        data: Dict[str, np.ndarray],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Export data to JSON format.

        Args:
            data: Dictionary of arrays to export
            output_path: Path to save JSON
            metadata: Optional metadata

        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            export_data: Dict[str, Any] = {}

            # Add metadata
            if self.config.include_metadata:
                export_data["_metadata"] = metadata or {}
                export_data["_metadata"]["export_time"] = datetime.now().isoformat()
                export_data["_metadata"]["format"] = "simulation_data"

            # Convert arrays to lists
            for key, array in data.items():
                if isinstance(array, np.ndarray):
                    export_data[key] = array.tolist()
                else:
                    export_data[key] = array

            # Add statistics
            if self.config.include_statistics:
                export_data["_statistics"] = self.compute_statistics(data)

            # Write JSON
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)

            return True

        except Exception as e:
            print(f"JSON export error: {e}")
            return False

    def export_hdf5(
        self,
        data: Dict[str, np.ndarray],
        output_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Export data to HDF5 format (efficient for large datasets).

        Args:
            data: Dictionary of arrays to export
            output_path: Path to save HDF5
            metadata: Optional metadata

        Returns:
            True if successful
        """
        try:
            import h5py

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with h5py.File(output_path, "w") as f:
                # Store metadata
                if self.config.include_metadata and metadata:
                    metadata_group = f.create_group("_metadata")
                    for key, value in metadata.items():
                        if isinstance(value, (str, int, float, bool)):
                            metadata_group.attrs[key] = value

                # Store data with compression
                for key, array in data.items():
                    if isinstance(array, np.ndarray):
                        chunks = True if array.size > 1_000_000 else None
                        compression = self.config.compression if self.config.compression != "none" else None
                        f.create_dataset(
                            key,
                            data=array,
                            compression=compression,
                            chunks=chunks,
                        )

                # Store statistics
                if self.config.include_statistics:
                    stats = self.compute_statistics(data)
                    stats_group = f.create_group("_statistics")
                    for key, value in stats.items():
                        if isinstance(value, (int, float, bool)):
                            stats_group.attrs[key] = value
                        elif isinstance(value, np.ndarray):
                            stats_group.create_dataset(key, data=value)

            return True

        except ImportError:
            print("h5py not available for HDF5 export")
            return False
        except Exception as e:
            print(f"HDF5 export error: {e}")
            return False

    def compute_statistics(self, data: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """
        Compute statistics on simulation data.

        Args:
            data: Dictionary of arrays

        Returns:
            Dictionary of computed statistics
        """
        stats: Dict[str, Any] = {}

        for key, array in data.items():
            if isinstance(array, np.ndarray) and array.size > 0:
                if np.issubdtype(array.dtype, np.number):
                    stats[f"{key}_mean"] = float(np.mean(array))
                    stats[f"{key}_std"] = float(np.std(array))
                    stats[f"{key}_min"] = float(np.min(array))
                    stats[f"{key}_max"] = float(np.max(array))
                    stats[f"{key}_count"] = int(array.size)

        return stats

    def export(
        self,
        data: Dict[str, np.ndarray],
        output_path: Path,
        format: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Export data in specified format.

        Args:
            data: Dictionary of arrays to export
            output_path: Path to save data
            format: Export format (uses config.format if None)
            metadata: Optional metadata

        Returns:
            True if successful
        """
        fmt = format or self.config.format

        if fmt == "csv":
            return self.export_csv(data, output_path, metadata)
        elif fmt == "json":
            return self.export_json(data, output_path, metadata)
        elif fmt == "hdf5":
            return self.export_hdf5(data, output_path, metadata)
        else:
            print(f"Unsupported format: {fmt}")
            return False

    def import_hdf5(self, input_path: Path) -> Dict[str, Any]:
        """
        Import data from HDF5 file.

        Args:
            input_path: Path to HDF5 file

        Returns:
            Dictionary with data and metadata
        """
        try:
            import h5py

            result: Dict[str, Any] = {}

            with h5py.File(input_path, "r") as f:
                # Read datasets
                for key in f.keys():
                    if not key.startswith("_"):
                        result[key] = np.array(f[key])

                # Read metadata
                if "_metadata" in f:
                    result["_metadata"] = dict(f["_metadata"].attrs)

                # Read statistics
                if "_statistics" in f:
                    stats = {}
                    for key in f["_statistics"].keys():
                        stats[key] = np.array(f["_statistics"][key])
                    for key, value in f["_statistics"].attrs.items():
                        stats[key] = value
                    result["_statistics"] = stats

            return result

        except ImportError:
            print("h5py not available for HDF5 import")
            return {}
        except Exception as e:
            print(f"HDF5 import error: {e}")
            return {}

    def import_json(self, input_path: Path) -> Dict[str, Any]:
        """
        Import data from JSON file.

        Args:
            input_path: Path to JSON file

        Returns:
            Dictionary with data and metadata
        """
        try:
            with open(input_path, "r") as f:
                data = json.load(f)

            # Convert lists back to numpy arrays
            result: Dict[str, Any] = {}
            for key, value in data.items():
                if isinstance(value, list):
                    result[key] = np.array(value)
                else:
                    result[key] = value

            return result

        except Exception as e:
            print(f"JSON import error: {e}")
            return {}
