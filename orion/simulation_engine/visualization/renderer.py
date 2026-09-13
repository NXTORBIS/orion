"""
Visualization Pipeline
State to graphics conversion, real-time rendering,
3D geometry integration, and animation output.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from pathlib import Path


@dataclass
class RenderConfig:
    """Configuration for visualization renderer."""
    width: int = 1280
    height: int = 720
    fps: int = 30
    backend: str = "matplotlib"  # matplotlib, plotly, pyopengl
    output_format: str = "png"  # png, mp4, gif
    camera_type: str = "orthographic"  # orthographic, perspective
    lighting: str = "phong"  # phong, flat, pbr
    colormap: str = "viridis"


class VisualizationRenderer:
    """
    Renders simulation state to graphics.
    Supports 2D/3D visualization, animations, and various export formats.
    """

    def __init__(self, config: RenderConfig):
        """
        Initialize renderer.

        Args:
            config: RenderConfig object
        """
        self.config = config
        self.frames: List[np.ndarray] = []
        self.frame_times: List[float] = []
        self.render_callbacks: Dict[str, callable] = {}

    def register_render_callback(
        self, simulation_type: str, callback: callable
    ) -> None:
        """
        Register custom render callback for simulation type.

        Args:
            simulation_type: Type of simulation (physics, social, etc.)
            callback: Rendering function
        """
        self.render_callbacks[simulation_type] = callback

    def render_2d(
        self,
        state: Dict[str, np.ndarray],
        time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """
        Render 2D visualization of state.

        Args:
            state: Simulation state dictionary
            time: Current simulation time
            metadata: Additional rendering metadata

        Returns:
            Rendered frame as numpy array (height x width x 3)
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.figure import Figure
            import matplotlib.patches as patches

            fig = Figure(figsize=(self.config.width / 100, self.config.height / 100))
            ax = fig.add_subplot(111)

            # Render particles/points
            if "positions" in state:
                positions = state["positions"]
                if positions.ndim == 2 and positions.shape[1] >= 2:
                    ax.scatter(
                        positions[:, 0],
                        positions[:, 1],
                        c="blue",
                        s=10,
                        alpha=0.6,
                    )

            # Render velocities as arrows
            if "velocities" in state and "positions" in state:
                velocities = state["velocities"]
                positions = state["positions"]
                if velocities.ndim == 2 and positions.ndim == 2:
                    ax.quiver(
                        positions[:, 0],
                        positions[:, 1],
                        velocities[:, 0],
                        velocities[:, 1],
                        alpha=0.3,
                        scale=50,
                    )

            ax.set_title(f"Simulation at t={time:.2f}s")
            ax.set_aspect("equal")
            ax.grid(True, alpha=0.3)

            # Convert to numpy array
            fig.canvas.draw()
            frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            frame = frame.reshape((self.config.height, self.config.width, 3))

            plt.close(fig)
            return frame

        except ImportError:
            # Fallback: create blank frame
            return np.zeros(
                (self.config.height, self.config.width, 3), dtype=np.uint8
            )

    def render_3d(
        self,
        state: Dict[str, np.ndarray],
        time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """
        Render 3D visualization of state.

        Args:
            state: Simulation state dictionary
            time: Current simulation time
            metadata: Additional rendering metadata

        Returns:
            Rendered frame as numpy array (height x width x 3)
        """
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            from matplotlib.figure import Figure

            fig = Figure(figsize=(self.config.width / 100, self.config.height / 100))
            ax = fig.add_subplot(111, projection="3d")

            # Render particles
            if "positions" in state:
                positions = state["positions"]
                if positions.ndim == 2 and positions.shape[1] >= 3:
                    ax.scatter(
                        positions[:, 0],
                        positions[:, 1],
                        positions[:, 2],
                        c="blue",
                        s=10,
                        alpha=0.6,
                    )
                elif positions.ndim == 2 and positions.shape[1] == 2:
                    # Fallback to 2D if only 2 coordinates
                    ax.scatter(
                        positions[:, 0],
                        positions[:, 1],
                        np.zeros(len(positions)),
                        c="blue",
                        s=10,
                        alpha=0.6,
                    )

            ax.set_title(f"3D Simulation at t={time:.2f}s")
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")

            # Convert to numpy array
            fig.canvas.draw()
            frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            frame = frame.reshape((self.config.height, self.config.width, 3))

            plt.close(fig)
            return frame

        except ImportError:
            # Fallback to 2D rendering
            return self.render_2d(state, time, metadata)

    def add_frame(
        self,
        state: Dict[str, np.ndarray],
        time: float,
        is_3d: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add frame to animation.

        Args:
            state: Simulation state
            time: Frame timestamp
            is_3d: Use 3D rendering
            metadata: Rendering metadata
        """
        if is_3d:
            frame = self.render_3d(state, time, metadata)
        else:
            frame = self.render_2d(state, time, metadata)

        self.frames.append(frame)
        self.frame_times.append(time)

    def export_frames(self, output_dir: Path, format: str = "png") -> None:
        """
        Export frames to disk.

        Args:
            output_dir: Directory to save frames
            format: Image format (png, jpg, etc.)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from PIL import Image

            for i, frame in enumerate(self.frames):
                img = Image.fromarray(frame.astype(np.uint8))
                img.save(output_dir / f"frame_{i:05d}.{format}")

        except ImportError:
            print("PIL not available for frame export")

    def create_animation(self, output_path: Path, fps: Optional[int] = None) -> bool:
        """
        Create animation file from frames.

        Args:
            output_path: Path to save animation
            fps: Frames per second (uses config.fps if None)

        Returns:
            True if successful
        """
        if not self.frames:
            print("No frames to animate")
            return False

        if fps is None:
            fps = self.config.fps

        try:
            if self.config.output_format == "gif":
                from PIL import Image

                images = [Image.fromarray(f.astype(np.uint8)) for f in self.frames]
                images[0].save(
                    output_path,
                    save_all=True,
                    append_images=images[1:],
                    duration=int(1000 / fps),
                    loop=0,
                )
                return True

            elif self.config.output_format == "mp4":
                import cv2

                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out = cv2.VideoWriter(
                    str(output_path),
                    fourcc,
                    fps,
                    (self.config.width, self.config.height),
                )

                for frame in self.frames:
                    # Convert RGB to BGR for OpenCV
                    frame_bgr = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_RGB2BGR)
                    out.write(frame_bgr)

                out.release()
                return True

            else:
                print(f"Unsupported format: {self.config.output_format}")
                return False

        except ImportError as e:
            print(f"Required library not available: {e}")
            return False

    def create_heatmap(
        self,
        data: np.ndarray,
        title: str = "Heatmap",
        cmap: str = "hot",
    ) -> np.ndarray:
        """
        Create heatmap visualization.

        Args:
            data: 2D array of values
            title: Heatmap title
            cmap: Colormap name

        Returns:
            Rendered heatmap as numpy array
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.figure import Figure

            fig = Figure(figsize=(self.config.width / 100, self.config.height / 100))
            ax = fig.add_subplot(111)

            im = ax.imshow(data, cmap=cmap, aspect="auto")
            ax.set_title(title)
            fig.colorbar(im, ax=ax)

            fig.canvas.draw()
            frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            frame = frame.reshape((self.config.height, self.config.width, 3))

            plt.close(fig)
            return frame

        except ImportError:
            return np.zeros(
                (self.config.height, self.config.width, 3), dtype=np.uint8
            )

    def clear_frames(self) -> None:
        """Clear animation frames."""
        self.frames.clear()
        self.frame_times.clear()

    def get_frame_count(self) -> int:
        """Get number of rendered frames."""
        return len(self.frames)
