# minxg R geometry adapter -- statistical geometry computations.
#
# R excels at statistical analysis of geometric data: point-cloud
# statistics, principal component analysis of shapes, KDE-based
# boundary estimation.  These scripts are called by RWorker when
# the AI needs R's statistical expertise for geometry tasks.
#
# License: MIT (same as project)

# ── Point cloud statistics ──────────────────────────────────

minxg_point_cloud_stats <- function(points) {
  # points: matrix or data.frame with columns x, y (and optionally z)
  if (!is.matrix(points) && !is.data.frame(points)) {
    stop("points must be a matrix or data.frame")
  }
  pts <- as.matrix(points)

  stats <- list(
    n = nrow(pts),
    centroid = colMeans(pts),
    covariance = cov(pts),
    eigenvalues = eigen(cov(pts))$values,
    eigenvectors = eigen(cov(pts))$vectors,
    bbox_min = apply(pts, 2, min),
    bbox_max = apply(pts, 2, max),
    bbox_size = apply(pts, 2, max) - apply(pts, 2, min),
    total_variance = sum(diag(cov(pts))),
    mean_distance_from_centroid = mean(
      sqrt(rowSums((pts - matrix(colMeans(pts), nrow(pts), ncol(pts), byrow = TRUE))^2))
    )
  )

  return(stats)
}

# ── Principal Component Analysis for shape orientation ────

minxg_pca_orientation <- function(points) {
  pts <- as.matrix(points)
  centered <- scale(pts, center = TRUE, scale = FALSE)
  pca <- prcomp(centered, center = FALSE, scale. = FALSE)

  return(list(
    principal_axes = pca$rotation,
    explained_variance = pca$sdev^2,
    explained_variance_ratio = pca$sdev^2 / sum(pca$sdev^2),
    scores = pca$x,
    centroid = attr(centered, "scaled:center")
  ))
}

# ── Kernel density estimation for boundary detection ───────

minxg_kde_boundary <- function(points, bandwidth = NULL) {
  pts <- as.matrix(points)
  if (ncol(pts) != 2) {
    stop("KDE boundary estimation requires 2D points")
  }

  if (is.null(bandwidth)) {
    bandwidth <- bw.nrd0(pts[, 1])  # Silverman's rule
  }

  # Create evaluation grid
  x_range <- range(pts[, 1])
  y_range <- range(pts[, 2])
  x_grid <- seq(x_range[1], x_range[2], length.out = 100)
  y_grid <- seq(y_range[1], y_range[2], length.out = 100)

  # 2D KDE
  kde <- MASS::kde2d(pts[, 1], pts[, 2], h = bandwidth, n = 100,
                     lims = c(x_range, y_range))

  return(list(
    density = kde,
    bandwidth = bandwidth,
    peak = which(kde$z == max(kde$z), arr.ind = TRUE),
    grid_x = kde$x,
    grid_y = kde$y
  ))
}

# ── Polygon area (R implementation for cross-validation) ──

minxg_polygon_area <- function(points) {
  pts <- as.matrix(points)
  if (ncol(pts) != 2 || nrow(pts) < 3) {
    stop("need >= 3 2D points")
  }
  n <- nrow(pts)
  cross_sum <- 0
  for (i in 1:n) {
    j <- if (i == n) 1 else i + 1
    cross_sum <- cross_sum + pts[i, 1] * pts[j, 2] - pts[j, 1] * pts[i, 2]
  }
  return(abs(cross_sum) / 2)
}
